from itertools import permutations
from operator import itemgetter
import statistics


def hamming_dist(x, y):
    return bin(x ^ y).count('1')

def hamming_weight(x):
    return bin(x).count('1')

def bitwise_mode(iterable, n):
    iter_bin = [bin(x)[2:].zfill(n) for x in iterable]
    modes = [statistics.mode(map(itemgetter(b), iter_bin)) for b in range(n)]
    return int(''.join(modes), 2)

def graycode(n):
    return n ^ (n >> 1)

def uniqueness(chip_dumps, response_len=1):
    def permute_chips(chip_dumps, response_len):
        for chip1, chip2 in permutations(chip_dumps, 2):
            distances = list()
            for challenge in chip1:
                resp1 = bitwise_mode(chip1[challenge], response_len)
                resp2 = bitwise_mode(chip2[challenge], response_len)
                distances.append(hamming_dist(resp1, resp2))
            yield statistics.mean(
                [distance/response_len for distance in distances]
            )

    k_chips = len(chip_dumps)
    if k_chips == 1:
        return 1
    sum_permutations = sum(permute_chips(chip_dumps, response_len))
    return 1 / (k_chips*(k_chips-1)) * sum_permutations

# for one chip
def steadiness(chip_dump, references, response_len=1):
    for challenge, responses in chip_dump.items():
        ref = references[challenge]
        distances = [hamming_dist(resp, ref) for resp in responses]
        # yield a value for each different challenge
        yield 1 - statistics.mean(
            [distance/response_len for distance in distances]
        )

def randomness():
    pass


import unittest


class EvaluationTestCase(unittest.TestCase):

    def setUp(self):
        self.chips_cr = [
            {
                'challenge1': [0,0,0,0],
                'challenge2': [0,0,0,0],
            },
            {
                'challenge1': [1,1,1,0],
                'challenge2': [0,0,0,0],
            },    
        ]

    def test_uniqueness(self):
        uniqueness_ = uniqueness(self.chips_cr, response_len=1)

    def test_steadiness(self):
        references = {
            'challenge1': 1,
            'challenge2': 0,
        }
        steadiness_ = steadiness(self.chips_cr[0], references, response_len=1)
