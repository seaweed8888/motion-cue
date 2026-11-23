import numpy as np
from sklearn.ensemble import RandomForestClassifier
from training.export_model import export
from .cpp import compile_cpp, run


def test_export_scores_and_labels(tmp_path):
    rng = np.random.default_rng(250)
    x = rng.normal(size=(200,55)).astype(np.float32)
    y = np.arange(200)%4
    model = RandomForestClassifier(n_estimators=20,max_depth=5,random_state=250).fit(x,y)
    export(dict(model=model, feature_version=1, threshold=.75, synthetic=True), tmp_path/"gesture_model.h")
    executable = compile_cpp(tmp_path, '''
#include "gesture_model.h"
#include <iostream>
#include <iomanip>
int main(){float x[55],p[4];while(std::cin>>x[0]){
for(int i=1;i<55;++i)std::cin>>x[i];gesture_model_predict_proba(x,55,p,4);
for(float v:p)std::cout<<std::setprecision(9)<<v<<" ";std::cout<<"\\n";}}
''', includes=[tmp_path])
    held_out = rng.normal(size=(50,55)).astype(np.float32)
    actual = np.fromstring(run(executable, held_out),sep=" ").reshape(-1,4)
    expected = model.predict_proba(held_out)
    np.testing.assert_allclose(actual, expected, atol=.012,rtol=0)
    # Quantized leaves can move near-ties; require agreement on clear winners.
    sorted_scores = np.sort(expected,axis=1)
    clear = sorted_scores[:,-1]-sorted_scores[:,-2] > .024
    np.testing.assert_array_equal(actual[clear].argmax(axis=1),expected[clear].argmax(axis=1))
