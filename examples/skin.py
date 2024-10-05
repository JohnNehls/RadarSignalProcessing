#!/usr/bin/env python

import matplotlib.pyplot as plt
from rsp import rdm
from rsp.rdm_helpers import plotRDM

################################################################################
# skin example
################################################################################
# - Matlab solution is incorrect due to not accounting for time-bandwidth prod in SNR
# - Matlab solution neglects range walk off, our SNR may be off when rangeRate>>0

tgt = {"range": 3.5e3, "rangeRate": 0.5e3, "rcs": 10}

bw = 10e6

radar = {
    "fcar": 10e9,
    "txPower": 1e3,
    "txGain": 10 ** (30 / 10),
    "rxGain": 10 ** (30 / 10),
    "opTemp": 290,
    "sampRate": 2 * bw,
    "noiseFig": 10 ** (8 / 10),
    "totalLosses": 10 ** (8 / 10),
    "PRF": 200e3,
    "dwell_time": 2e-3,
}

wvf = {"type": "lfm", "bw": bw, "T": 1.0e-6, "chirpUpDown": 1}


return_list = [{"type": "skin"}]

rdot_axis, r_axis, total_dc, _, _ = rdm.rdm_gen(
    tgt, radar, wvf, return_list, seed=0, plotSteps=True
)

plotRDM(rdot_axis, r_axis, total_dc, f"Total RDM for {wvf['type']}")

plt.show()
