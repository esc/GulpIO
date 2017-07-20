#!/usr/bin/env python
"""Create a binary file including all video frames with RecordIO convention.
Usage:
  create_binary from_video [<videos_path>] [<csv_file>|<input_json>] [<output_folder>] [<video_per_chunk>] [<image_size>] [<temp_dir>] [<labels>]
  create_binary from_frames [<frames_path>] [<csv_file>|<input_json>] [<output_folder>] [<video_per_chunk>] [<image_size>] [<labels>]
  create_binary (-h | --help)
  create_binary --version
Options:
  -h --help     Show this screen.
  --version     Show version.
  json_file     paths to json files
"""

import os
import pickle
import glob
import cv2
import pandas as pd
import numpy as np
import docopt

from tqdm import tqdm
from joblib import Parallel, delayed
from concurrent.futures import ProcessPoolExecutor, as_completed

from gulpio.gulpio import GulpVideoIO
from gulpio.utils import resize_by_short_edge, shuffle, burst_frames_to_shm
from gulpio.parse_input import Input_from_csv, Input_from_json

#shm_dir_path (input docopt)

def initialize_filenames(output_folder, chunk_no):
    bin_file_path = os.path.join(output_folder, 'data{}.bin'.format(chunk_no))
    meta_file_path = os.path.join(output_folder, 'meta{}.bin'.format(chunk_no))
    return bin_file_path, meta_file_path


def get_video_as_label_and_frames(entry):
    #if("youtube_id" not in entry or  TODO: uncomment this
    #   "label" not in entry or
    #   "time_start" not in entry or
    #   "end_time" not in entry):
    #    print("{} is not complete!".format(entry))
    video_id = entry['id']
    label = entry['label']
    folder = create_folder_name(video_id,
                                video_path=video_path,
                                label=label,
                                start_t=entry['start_time'],
                                end_t=entry['end_time'])
    imgs = find_jpgs_in_folder(folder)
    if not check_frames_are_present(imgs):
        if check_mp4_file_present(get_video_path(folder)):
            imgs = burst_video_into_frames(get_video_path(folder)[0],
                                           shm_dir_path)
        else:
            print("neither video nor frames are present in {}".format(folder))
    if dump_labels2idx_in_pickel:
        label_idx = labels2idx[label]
    else:
        label_idx = -1
    return video_id, imgs, label_id, label

def create_folder_name(video_id, video_path=None, label=None, start_t=None,
                       end_t=None):
    if video_path:
        return os.path.join(vid_path, video_id)
    return os.path.join(args.frames_path,
                        label,
                        video_id) + "_{:06d}_{:06d}".format(start_t, end_t)



def find_jpgs_in_folder(folder):
    return sorted(glob.glob(folder + '/*.jpg'))


def check_frames_are_present(imgs, temp_dir=None):
    if len(imgs) == 0:
        print("No frames present...")
        if temp_dir:
            shutil.rmtree(temp_dir)
        continue

def get_video_path(folder):
    return glob.glob(folder_name + "*.mp4")

def check_one_mp4_file_present(vid_path):
    if len(vid_path) > 1:
        print("more than one video file in {}".format(vid_path))
        return False
    if not os.path.isfile(vid_path[0]):
        print("no video file {}".format(vid_path))
        return False
    return True


def get_resized_image(imgs, img_size):
    for img in imgs:
        img = cv2.imread(img)
        img = resize_by_short_edge(img, img_size)
        yield img


def burst_video_into_frames(vid_path, shm_dir_path):
    temp_dir = burst_frames_to_shm(vid_path, shm_dir_path)
    imgs = sorted(glob.glob(temp_dir + '/*.jpg'))
    check_frames_are_present(imgs, temp_dir)
    clear_temp_dir(temp_dir)
    return imgs

def clear_temp_dir(temp_dir):
    shutil.rmtree(temp_dir)

def create_chunk(inputs):
    df, output_folder, chunk_no, img_size = inputs
    bin_file_path, meta_file_path = initialize_filenames(output_folder,
                                                         chunk_no)
    gulp_file = GulpVideoIO(bin_file_path, 'wb', meta_file_path)
    gulp_file.open()
    for idx, row in enumerate(df):
        video_id, imgs, label_idx, label = get_video_as_label_and_frames(row)
        #ensure_frames_are_present(imgs)
        [gulp_file.write(label_idx, video_id, img)
            for img in get_resized_image(imgs, img_size)]
    gulp_file.close()
    return True


def parallel_process(array, function, n_jobs=16, use_kwargs=False, front_num=0):
    """
        A parallel version of the map function with a progress bar. 
        Args:
            array (array-like): An array to iterate over.
            function (function): A python function to apply to the elements of array
            n_jobs (int, default=16): The number of cores to use
            use_kwargs (boolean, default=False): Whether to consider the elements of array as dictionaries of 
                keyword arguments to function 
            front_num (int, default=3): The number of iterations to run serially before kicking off the parallel job. 
                Useful for catching bugs
        Returns:
            [function(array[0]), function(array[1]), ...]
    """
    # Assemble the workers
    with ProcessPoolExecutor(max_workers=n_jobs) as pool:
        # Pass the elements of array into function
        futures = [pool.submit(function, a) for a in array[front_num:]]
        kwargs = {
            'total': len(futures),
            'unit': 'it',
            'unit_scale': True,
            'leave': True
        }
        # Print out the progress as tasks complete
        for f in tqdm(as_completed(futures), **kwargs):
            pass
    out = []
    # Get the results from the futures.
    for i, future in tqdm(enumerate(futures)):
        try:
            out.append(future.result())
        except Exception as e:
            out.append(e)
    return front + out


def ensure_output_dir_exists(output_dir):
    os.makedirs(output_dir, exist_ok=True)



def dump_labels_in_pickel(labels_idx):
    pickle.dump(labels2idx, open(output_folder + '/label2idx.pkl', 'wb'))


if __name__ == '__main__':
	arguments = docopt(__doc__)
	if arguments['from_video']:
		videos_path = arguments['<video_path>'] # help=('Path to videos'))
		shm_dir_path = arguments['<temp_dir>'] # help='path to the temp directory in shared memory.')
	if arguments['from_frames']:
		frames_path = arguments['<frames_path>'] # help=('Path to bursted frames'))

	input_csv = arguments['<input_csv>'] # help=('Kinetics CSV file containing the following format:                             'YouTube Identifier,Start time,End time,Class label'))
    input_json = arguments['<input_json>'] #  help=('path to the json file to convert the videos for (train/validation/test)'))
    output_folder = arguments['<output_folder>'] #  help='Output folder')
    vid_per_chunk = arguments['<videos_per_chunk>'] # help='number of videos in a chunk')
    num_workers = arguments['<num_workers>'] # help='number of workers.')
    img_size = arguments['image_size'] # help='shortest img size to resize all input images.')
    dump_label2idx = arguments['<label>']
    # create output folder if not there
    ensure_output_dir_exists(output_folder)


    # read data
    if input_csv:
        data_object = Input_from_csv(input_csv)
    elif input_json:
        data_object = Input_from_json(input_json)
    # create label to idx map
    if dump_label2idx:
        labels2idx = data_object.label2idx
        print(" > Creating label dictionary")
        dump_labels2idx_in_pickel(label2idx)

    data = data_object.get_data()

    num_chunks = len(data) // vid_per_chunk + 1

    # shuffle df and write binary file
    print(" > Shuffling data list")
    data = shuffle(data)

    # set input array
    print(" > Setting up data chunks")
    inputs = []

    for chunk_id in range(num_chunks):
        if chunk_id == num_chunks - 1:
            df_sub = data[chunk_id * .vid_per_chunk:]
        else:
            df_sub = data[chunk_id * vid_per_chunk:
                          (chunk_id + 1) * vid_per_chunk]
        input_data = [df_sub, output_folder, chunk_id, img_size]
        inputs.append(input_data)


    print(" > Chunking started!")
    #parallel_process(inputs, create_chunk, n_jobs=args.num_workers)
    results = Parallel(n_jobs=num_workers)(delayed(create_chunk)(i)
                                           for i in tqdm(inputs))
