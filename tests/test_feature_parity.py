import json
from pathlib import Path
import numpy as np
from training.features import extract
from .cpp import compile_cpp, run


def test_feature_parity(tmp_path):
    executable = compile_cpp(tmp_path, '''
#include "motioncue.h"
#include <iostream>
#include <iomanip>
int main(){std::vector<motioncue::Sample> s;motioncue::Sample r;
while(std::cin>>r.t){for(float& x:r.axis)std::cin>>x;s.push_back(r);}
for(float x:motioncue::features(s))std::cout<<std::setprecision(9)<<x<<" ";}
''', ["firmware/src/features.cpp"])
    samples = json.loads(Path("tests/fixtures/window.json").read_text())
    actual = np.fromstring(run(executable, samples), sep=" ")
    np.testing.assert_allclose(actual, extract(samples), rtol=2e-5, atol=2e-5)
