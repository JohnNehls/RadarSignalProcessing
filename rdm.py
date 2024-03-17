#!/usr/bin/env python

import numpy as np
from scipy import fft
from scipy import signal
import matplotlib.pyplot as plt
from rdm_helpers import plotRDM, plotRTM
from pulse_doppler_radar import range_unambiguous, frequency_doppler, frequency_aliased
from rf_datacube import calc_range_axis, create_dataCube, dopplerProcess_dataCube, R_pf_tgt
from rf_datacube import applyMatchFilterToDataCube
from waveform import makeBarkerCodedPulse, makeLFMPulse, makeRandomCodedPulse, makeUncodedPulse
from waveform_helpers import insertWvfAtIndex
from range_equation import snr_rangeEquation, snr_rangeEquation_CP
from noise import band_limited_complex_noise

################################################################################
# notes:
################################################################################
# - Need to decide if radar parameters are added in dB and when to convert
#   - Volts -> dB: 10+ log10( abs (Volts) **2 )
# - Why does noise have SNR > 1 in final noise RDM?
# - Pedantic direct match filter is cleaner in phase (zeros where there is no signal)
# - Could modify freq due to doppler using frequence_doppler function.. Flag?
# - Make pulsewidth/2 range offset clearer
# - range bins are A/D samples
# - Break into smaller funcitons:
#   - signal gen?
# - Could make wvf class with BW, pulse_length, time_BW_product attributes
# - make non-skin returns range and range/rate agnostic

################################################################################
# comparison to MATLAB solutions
################################################################################
# - solution SNR does not depend on time-BW product-- assumes it is 1 for all wvfms
# - solution does not account for pulseWidth/2 range offest in range

################################################################################
# future
################################################################################
# - make a pod (seperate from skin) at the same range as target

# constants
C = 3e8
PI = np.pi

def rdm_gen(tgtInfo: dict, radar: dict, wvf: dict, Npulses: int, returnInfo: dict,
            seed=None, plotSteps=False):
    """
    Genearat a CPI RDM for single target moving at a constant range rate.

    Parameters
    ----------
    tgtInfo: dict holding range, rangeRate, and rcs (range rate and rcs constant for CPI)
    radar: dict holding fcar, txPower, txGain, rxGain, opTemp, sampRate, noiseFig, totalLosses, PRF
    wvf: string for wvform types : "uncoded" "barker" "random" "lfm"
    Npulses: number of puleses in the CPI

    Returns
    -------
    rdot_axis: array of rangeRate axis [m/s]
    r_axis: range axisk [m]
    total_dc: RDM in Volts for noise + signal
    signal_dc: RDM in Volts for signal
    noise_dc: RDM in Volts for noise
    """

    t_ar = np.arange(Npulses)*1/radar["PRF"]

    ################################################################################
    #0 Set random seed
    ################################################################################
    if seed != None:
        print (f"{seed=}")
        np.random.seed(seed)

    ################################################################################
    #1 Create signal datacube
    ################################################################################
    signal_dc = create_dataCube(radar["sampRate"], radar["PRF"], Npulses, noise=False)
    r_axis = calc_range_axis(radar["sampRate"], signal_dc.shape[0])

    ################################################################################
    #2 Range and range rate of the target ######
    ################################################################################
    # Currently takes in constant range rate
    range_ar = tgtInfo["range"] + tgtInfo["rangeRate"]*t_ar

    ################################################################################
    #3 First response pulse location
    ################################################################################
    firstEchoBin = int(tgtInfo["range"]/range_unambiguous (radar ["PRF"]))

    ################################################################################
    #4 Waveform
    ################################################################################
    # Q: Should I normalize pulses? Yes, the time-bandwidth poduct is used for amp
    # A: Yes, the time-bandwidth poduct is used for amp scaling in step 5.
    if wvf["type"] == "uncoded":
        _, pulse_wvf = makeUncodedPulse(radar['sampRate'], wvf['bw'])
        BW = wvf['bw']
        time_BW_product = 1
        pulse_width = 1/wvf["bw"]

    elif wvf["type"] == "barker":
        _, pulse_wvf = makeBarkerCodedPulse(radar ['sampRate'], wvf['bw'], wvf["nchips"])
        BW = wvf['bw']
        time_BW_product = wvf["nchips"]
        pulse_width = 1/wvf["bw"]*wvf ["nchips"]

    elif wvf["type"] == "random":
        _, pulse_wvf = makeRandomCodedPulse(radar ['sampRate'], wvf['bw'], wvf["nchips"])
        BW = wvf['bw']
        time_BW_product = wvf ["nchips"]
        pulse_width = 1/wvf["bw"]*wvf ["nchips"]

    elif wvf["type"] == "lfm":
        _, pulse_wvf = makeLFMPulse(radar ['sampRate'], wvf['bw'], wvf['T'], wvf['chirpUpDown'])
        BW = wvf ['bw']
        time_BW_product = wvf ["bw"]*wvf["T"]
        pulse_width = wvf["T"]

    else:
        print("wvf type not found: no pulse added")
        pulse_wvf = np.array([1])
        BW = 1
        time_BW_product = 1
        pulse_width = 1

    ################################################################################
    #5 Determin scaling factor for SNR
    ################################################################################
    # Motivation: direclty plot the RDM in SNR by way of the range equation
    # notes:
    # - The SNR is calculated at the initial range and does not change in time

    # SNR for one pulse
    SNR1 = snr_rangeEquation(radar["txPower"], radar["txGain"], radar["rxGain"],
                             tgtInfo["rcs"], C/radar["fcar"], tgtInfo["range"],
                             BW, radar["noiseFig"], radar["totalLosses"],
                             radar["opTemp"], time_BW_product)

    SNR_volt = np.sqrt(SNR1/Npulses)

    # calculated to check we see the expected SNR SNR_expected
    SNR_expected = snr_rangeEquation_CP(radar["txPower"], radar["txGain"],
                                        radar["rxGain"], tgtInfo["rcs"],
                                        C/radar["fcar"], tgtInfo["range"], BW,
                                        radar["noiseFig"], radar["totalLosses"],
                                        radar["opTemp"], Npulses, time_BW_product)
    print (f"SNR Check: ")
    print(f"\t{10*np.log10(SNR1)=:.2f}")
    print(f"\t{SNR_volt=:.1e}\n\t{SNR_expected=:.1e}")
    print(f"\t{10*np.log10(SNR_expected)=:.2f}")

    ################################################################################
    #6 Place pulse at range index and apply phase
    ################################################################################
    ## pulses timed from their start not their center, we compensate with pw/2 range offset
    r_pwOffset = pulse_width/2*C/2

    aliasedRange_ar = range_ar%range_unambiguous(radar["PRF"])
    phase_ar = -4*PI*radar["fcar"]/C*range_ar

    if returnInfo["type"] == "VBM":
        #Achieve Velocity Bin Masking (VBM) by adding pahse in slow time
        # - want to add phase so wvfm will sill pass radar's match filter

        #convert rdot_delta to a frequency delta
        f_delta = 2*radar["fcar"]/C*returnInfo["rdot_delta"]

        #Method 1 : add random phase to each pulse
        # - does not require assumption on processing interval
        # - dirty result
        # band_noise = band_limited_complex_noise(-f_delta/2, +f_delta/2, Npulses, radar["PRF"],
        #                                         normalize=True)

        #Method 2 : use LFM in slow time
        _, band_noise = makeLFMPulse(radar["PRF"], f_delta, Npulses/radar["PRF"], 1,
                                     normalize=False)


    for i in range(Npulses-firstEchoBin):
        # TODO is this how these should be binned? Should they be interpolated onto grid?
        rangeIndex = np.argmin(abs(r_axis - aliasedRange_ar[i] + r_pwOffset))

        if returnInfo["type"] == "skin":
            pulse= SNR_volt*pulse_wvf*np.exp(1j*phase_ar[i])

        elif returnInfo["type"] == "VBM":
            pulse= SNR_volt*pulse_wvf*np.exp(1j*phase_ar[i])*band_noise[i]

        else:
            print(f"{returnInfo["type"]=} not known, no return added.")
            pulse = np.zeros(1)

        signal_dc[:,i+firstEchoBin] += insertWvfAtIndex(signal_dc[:,i+firstEchoBin], pulse,
                                                   rangeIndex)

    ################################################################################
    #7 Create noise and total datacube
    ################################################################################
    noise_dc = create_dataCube(radar["sampRate"], radar["PRF"], Npulses, noise=True)

    print(f"\n5.3.2 noise check: {np.var(fft.fft(noise_dc, axis=1))=: .4f}")

    total_dc = signal_dc + noise_dc

    if plotSteps:
        plotRTM(r_axis, signal_dc, f"SIGNAL: unprocessed {wvf["type"]}")

    ################################################################################
    #8 Apply the match filter
    ################################################################################
    applyMatchFilterToDataCube(signal_dc, pulse_wvf)
    applyMatchFilterToDataCube(noise_dc, pulse_wvf)
    applyMatchFilterToDataCube(total_dc, pulse_wvf)

    if plotSteps:
        plotRTM(r_axis, signal_dc, f"SIGNAL: match filtered {wvf["type"]}")
        # plotRTM(r_axis, noise_dc,   f"NOISE: match filtered {wvf["type"]}")
        # plotRTM(r_axis, total_dc,   f"TOTAL: match filtered {wvf["type"]}")

    ################################################################################
    #9 Doppler process
    ################################################################################
    # create filter window ###############
    chwin = signal.windows.chebwin(Npulses, 60)
    chwin_norm = chwin/np.mean(chwin)
    chwin_norm = chwin_norm.reshape((1, chwin.size))
    tmp = np.ones((total_dc.shape[0],1))
    chwin_norm_mat = tmp@chwin_norm

    # apply filter window ###############
    total_dc = total_dc*chwin_norm_mat
    signal_dc = signal_dc*chwin_norm_mat

    # if plotSteps:
        # plotRTM(r_axis, signal_dc, f"SIGNAL: mf & windowed {wvf["type"]}")
        # plotRTM(r_axis, total_dc,   f"TOTAL: mf & windowed {wvf["type"]}")

    # doppler process ######### #####################
    f_axis, r_axis = dopplerProcess_dataCube(signal_dc, radar["sampRate"], radar["PRF"])
    _, _           = dopplerProcess_dataCube(noise_dc,  radar["sampRate"], radar["PRF"])
    _, _           = dopplerProcess_dataCube(total_dc,  radar["sampRate"], radar["PRF"])

    # calc rangeRate axis #*#**######################
    #f = -2* fc/c Rdot -> Rdot = -c+f/ (2+fc)
    #TODO WHY PRF/fs ratio at end??!?!
    rdot_axis = -C*f_axis/(2*radar["fcar"])*radar["PRF"]/radar["sampRate"]

    ################################################################################
    # Verify SNR and noise
    ################################################################################
    print(f"\nnoise check:")
    noise_var = np.var (total_dc, 1)
    print(f"\t{np.mean (noise_var)=: .4f}")
    print(f"\t{np.var(noise_var)=: .4f}")
    print(f"\t{np.mean (20*np.log10(noise_var))=: .4f}")
    print(f"\t{np.var (20*np.log10(noise_var))=: .4f}")
    print(f"\nSNR test:")
    print(f"\t{20*np.log10(np.max(abs(signal_dc)))=:.2f}")
    print(f"\t{20*np.log10(np.max(abs(noise_dc)))=:.2f}")
    print (f"\t{20*np.log10(np.max(abs(total_dc)))=:.2f}")

    return rdot_axis, r_axis, total_dc, signal_dc, noise_dc

plt.close('all')

################################################################################
# Function inputs
################################################################################
bw = 10e6

tgtInfo = {"range": 3.5e3,
           "rangeRate": 0e3,
           "rcs" : 10}

radar = {"fcar" : 10e9,
         "txPower": 1e3,
         "txGain" : 10**(30/10),
         "rxGain" : 10**(30/10),
         "opTemp": 290,
         "sampRate": 2*bw,
         "noiseFig": 10**(8/10),
         "totalLosses" : 10**(8/10),
         "PRF": 200e3}

wvf = {"type" : None} # noise test

wvf = {"type": "uncoded",
       "bw" : bw}

wvf = {"type" : "barker",
       "nchips" : 13,
       "bw" : bw}

# # wvf = {"type": "random",
#        "nchips" : 13,
#        "bw" : bw}

# wvf = {"type": "lfm",
#        "bw" : bw,
#        "T": 10/40e6,
#        'chirpUpDown': 1}

returnInfo = {"type" : "skin"}
returnInfo = {"type" : "VBM",
              "rdot_delta" : 1e3}

dwell_time = 2e-3
Npulses = int(np.ceil(dwell_time* radar ["PRF"]))
plotsteps = True

################################################################################
## Call function
################################################################################
rdot_axis, r_axis, total_dc, signal_dc, noise_dc = rdm_gen(tgtInfo, radar,
                                                           wvf, Npulses,
                                                           returnInfo,
                                                           seed=0,
                                                           plotSteps=True)

################################################################################
## Plot outputs
################################################################################
plotRDM(rdot_axis, r_axis, signal_dc, f"SIGNAL: dB doppler processed match filtered {wvf["type"]}")
plotRDM(rdot_axis, r_axis, total_dc, f"TOTAL: dB doppler processed match filtered {wvf["type"]}", cbarRange=False)
# plotRDM(rdot_axis, r_axis, noise_dc, f"NOISE: dB doppler processed match filtered {wvf["type"]}")

plt.show()
