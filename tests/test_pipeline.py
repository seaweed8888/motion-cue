import json
from pathlib import Path
import numpy as np
import pytest
from training.features import extract
from training.preprocess import segment
from training.train import split_events
from .cpp import compile_cpp, run


def test_segmentation_and_mode(tmp_path):
    samples = json.loads(Path("data/sample/continuous.json").read_text())["samples"]
    expected = list(segment(samples))
    assert len(expected)==1
    executable=compile_cpp(tmp_path, '''
#include "motionlink.h"
#include <cassert>
#include <iostream>
int main(){motionlink::ControlMode m;assert(!m.gesture(1));assert(!m.gesture(3));
assert(m.armed);assert(m.gesture(1));assert(!m.gesture(3));assert(!m.armed);
motionlink::Session connection;connection.pulse("one","a",0);connection.mode.armed=true;
connection.tick(1201);assert(!connection.mode.armed);assert(!connection.live);
connection.pulse("two","b",1300,"stale-arm",true);assert(!connection.mode.armed);
assert(motionlink::classify(motionlink::Features{})==0);
motionlink::Segmenter s;motionlink::Sample r;int count=0;
while(std::cin>>r.t){for(float& x:r.axis)std::cin>>x;if(s.push(r))++count;}
std::cout<<count;}
''', ["firmware/src/segmenter.cpp","firmware/src/control_mode.cpp","firmware/src/mqtt_client.cpp",
      "firmware/src/main.cpp","firmware/src/features.cpp","firmware/src/classifier.cpp","firmware/src/imu.cpp"])
    assert int(run(executable,samples))==len(expected)
    still=np.zeros((400,7),dtype=np.float32);still[:,0]=np.arange(400)/100;still[:,3]=9.81
    assert list(segment(still))==[]
    assert int(run(executable,still))==0
    still[:,4]=2
    assert list(segment(still))==[]
    assert int(run(executable,still))==0


def test_invalid_features_and_split_leakage():
    with pytest.raises(ValueError):extract([[0]*7]*3)
    with pytest.raises(ValueError):split_events([],{"train":["a"],"validation":["a"],"test":["b"]})
