#!/usr/bin/env python

from .constants import PI, C, K_BOLTZ

def snr_rangeEquation_uncoded(Pt, Gt, Gr, sigma, wavelength, R, B, F, L, T):
    """Single-pulse SNR for uncoded pulse"""
    return (Pt*Gt*Gr*sigma*wavelength**2)/(((4*PI)**3)*(R**4)*K_BOLTZ*T*B*F*L)

def snr_rangeEquation(Pt, Gt, Gr, sigma, wavelength, R, B, F, L, T, time_bandwidth_prod):
    """Single-pulse SNR"""
    return snr_rangeEquation_uncoded(Pt, Gt, Gr, sigma, wavelength, R, B, F, L, T)*time_bandwidth_prod

def snr_rangeEquation_CP(Pt, Gt, Gr, sigma, wavelength, R, B, F, L, T, n_p,
                         time_bandwidth_prod):
    """"SNR of range equation with coherent processing (CP)"""
    singlePulse_snr= snr_rangeEquation(Pt, Gt, Gr, sigma, wavelength, R, B, F, L, T, time_bandwidth_prod)
    return singlePulse_snr*n_p


def snr_rangeEquation_BPSK_pulses(Pt, Gt, Gr, sigma, wavelength, R, B, F, L, T, n_p, n_c):
    """"SNR of range equation with coherent processing (CP)
    \tn_p := number of pulses
    \tn_c := number of chips
    """
    return snr_rangeEquation_CP(Pt, Gt, Gr, sigma, wavelength, R, B, F, L, T, n_p, n_c)


def snr_rangeEquation_dutyFactor_pulses(Pt, Gt, Gr, sigma, wavelength, R, F, L, T,
                                        Tcpi, tau_df):
    """"SNR of range equation with coherent processing in duty factor form
    \tTcpi := Total time of coherent processing interval (CPI) in seconds
    \ttau_df := duty factor, in [0,1]
    """
    singlePulse_snr= snr_rangeEquation_uncoded(Pt, Gt, Gr, sigma, wavelength, R, 1, F, L, T)
    return singlePulse_snr*Tcpi*tau_df


def minTargetDetectionRange(Pt, Gt, Gr, sigma, wavelength, SNR_thresh, B, F, L, T):
    """single pulse minimum detectable range for a SNR_threshold"""
    return ((Pt*Gt*Gr*sigma*wavelength**2)/(((4*PI)**3)*(SNR_thresh)*K_BOLTZ*T*B*F*L))**(1/4)


def minTargetDetectionRange_BPSK_pulses(Pt, Gt, Gr, sigma, wavelength, SNR_thresh, B, F,
                                        L, T, n_p, n_c):
    """Minimum detectable range for a SNR_threshold for BPSK pulses
    \tn_p := number of pulses
    \tn_c := number of chips
    """
    onePulse = minTargetDetectionRange(Pt, Gt, Gr, sigma, wavelength, SNR_thresh, B, F, L, T)
    return onePulse*(n_p*n_c)**(1/4)


def minTargetDetectionRange_dutyFactor_pulses(Pt, Gt, Gr, sigma, wavelength, SNR_thresh,
                                              F, L, T, Tcpi, tau_df):
    """Minimum detectable range for a SNR_threshold for BPSK pulses
    \tTcpi := Total time of coherent processing interval (CPI) in seconds
    \tau_df := duty factor, in [0,1]
    """
    onePulse = minTargetDetectionRange(Pt, Gt, Gr, sigma, wavelength, SNR_thresh, 1, F, L, T)
    return onePulse*(Tcpi*tau_df)**(1/4)