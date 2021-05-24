from itertools import permutations
import argparse
from glob import glob
import json
import statistics
from operator import sub
from itertools import starmap
import ctypes

from more_itertools import all_equal

from .stats import steadiness, uniqueness, graycode


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('dump_files', nargs='*')

    args = parser.parse_args()

    dump_files = list()
    for arg in args.dump_files:  
        dump_files += glob(arg)
    print(dump_files)

    response_dumps = []
    for filename in dump_files:
        with open(filename, 'r') as f:
            response_data = json.load(f)

        cell1 = response_data['teropuf_cell0_select_storage']
        cell2 = response_data['teropuf_cell1_select_storage']
        select1 = response_data['teropuf_roset0_select']
        select2 = response_data['teropuf_roset1_select']
        assert(all_equal(select1))
        assert(all_equal(select2))
        challenge = f'{select1[0]}:{select2[0]}'

        # each clock cycles has two values (rising, falling), skip every other value
        counter1 = response_data['teropuf_roset0_counter'][::2] 
        counter2 = response_data['teropuf_roset1_counter'][::2]
        responses_sub = starmap(sub, zip(counter1, counter2))
        responses = [ctypes.c_uint16(r).value for r in responses_sub]
        responses_gray = map(graycode, responses)

        response_dumps.append(list(responses_gray))
