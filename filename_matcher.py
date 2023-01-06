import PTN
import os
from typing import List, Callable


def parse_fname(fn: str) -> dict:
    return PTN.parse(os.path.basename(fn))

# ------------------------------------------------------


class FilenameMatcher:
    """ Match between filenames based on parsable attributes """

    def __init__(self):
        self._metric = AttribMatchMetric()

    def calc_match_scores(self, fn1: str, fns2: List[str]) -> List[float]:
        """ returns scores vector such that scores[i] = match_score(fn1, fns2[i]) """
        a1 = parse_fname(fn1)
        return [self._metric(a1, parse_fname(fn2)) for fn2 in fns2]

    def get_best_match_ix(self, fn1: str, fns2: List[str]):
        """ index of best match to filename fn1 amongst list fn2
            if best match is below threshold, returns None
        """
        scores = self.calc_match_scores(fn1, fns2)
        max_score = max(scores)
        if max_score < self._metric.thresh:
            return None
        return scores.index(max_score)


class AttribMatchMetric:
    """ Pairwise match metric between set of attributes """

    def __init__(self):

        self._missing_key_factor = .5
        self._metric_weights = {
            'quality': 5,
            'codec': 1.5,
            'resolution': 1,
            'encoder': 1,
            'audio': .5
        }
        self._thresh = 2

    @property
    def thresh(self):
        return self._thresh

    def __call__(self, a1: dict, a2: dict) -> float:
        score = 0
        for k, w in self._metric_weights.items():
            if k in a1 and k in a2:
                score += w * float(a1[k] == a2[k])
            else:
                score += w * self._missing_key_factor
        return score
