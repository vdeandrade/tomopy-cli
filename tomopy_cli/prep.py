import tomopy
import numpy as np

from tomopy_cli import log


def data(proj, flat, dark, params):
    # zinger_removal
    proj, flat = zinger_removal(proj, flat, params)

    if (params.dark_zero):
        dark *= 0
        log.warning('  *** *** dark fields are ignored')

    # normalize
    data = flat_correction(proj, flat, dark, params)
    # remove stripes
    data = remove_stripe(data, params)
    # phase retrieval
    data = phase_retrieval(data, params)
    # minus log
    data = minus_log(data, params)
    # remove outlier
    data = remove_nan_neg_inf(data, params)

    return data


def remove_nan_neg_inf(data, params):

    log.info('  *** remove nan, neg and inf')
    if(params.fix_nan_and_inf == True):
        log.info('  *** *** standard')
        log.info('  *** *** replacement value %f ' % params.fix_nan_and_inf_value)
        data = tomopy.remove_nan(data, val=params.fix_nan_and_inf_value)
        data = tomopy.remove_neg(data, val=params.fix_nan_and_inf_value)
        data[np.where(data == np.inf)] = params.fix_nan_and_inf_value
    else:
        log.warning('  *** *** none')

    return data

def zinger_removal(proj, flat, params):

    log.info("  *** zinger removal")
    if (params.zinger_removal_method == 'standard'):
        log.info('  *** *** standard')
        log.info("  *** *** zinger level projections: %d" % params.zinger_level_projections)
        log.info("  *** *** zinger level white: %s" % params.zinger_level_white)
        log.info("  *** *** zinger_size: %d" % params.zinger_size)
        proj = tomopy.misc.corr.remove_outlier(proj, params.zinger_level_projections, size=params.zinger_size, axis=0)
        flat = tomopy.misc.corr.remove_outlier(flat, params.zinger_level_white, size=params.zinger_size, axis=0)
    elif(params.zinger_removal_method == 'none'):
        log.warning('  *** *** none')

    return proj, flat


def flat_correction(proj, flat, dark, params):

    log.info('  *** normalization')
    if(params.flat_correction_method == 'standard'):
        data = tomopy.normalize(proj, flat, dark, cutoff=params.normalization_cutoff)
        log.info('  *** *** standard %f cut-off' % params.normalization_cutoff)
    elif(params.flat_correction_method == 'air'):
        data = tomopy.normalize_bg(proj, air=params.air)
        log.info('  *** *** air %d pixels' % params.air)
    elif(params.flat_correction_method == 'none'):
        data = proj
        log.warning('  *** *** normalization is turned off')

    return data

def remove_stripe(data, params):

    log.info('  *** remove stripe:')
    if(params.remove_stripe_method == 'fw'):
        log.info('  *** *** fourier wavelet')
        data = tomopy.remove_stripe_fw(data,level=params.fw_level,wname=params.fw_filter,sigma=params.fw_sigma,pad=params.fw_pad)
        log.info('  *** ***  *** fw level %d ' % params.fw_level)
        log.info('  *** ***  *** fw wname %s ' % params.fw_filter)
        log.info('  *** ***  *** fw sigma %f ' % params.fw_sigma)
        log.info('  *** ***  *** fw pad %r ' % params.fw_pad)
    elif(params.remove_stripe_method == 'ti'):
        log.info('  *** *** titarenko')
        data = tomopy.remove_stripe_ti(data, nblock=params.ti_nblock, alpha=params.ti_alpha)
        log.info('  *** ***  *** ti nblock %d ' % params.ti_nblock)
        log.info('  *** ***  *** ti alpha %f ' % params.ti_alpha)
    elif(params.remove_stripe_method == 'sf'):
        log.info('  *** *** smoothing filter')
        data = tomopy.remove_stripe_sf(data,  size==params.sf_size)
        log.info('  *** ***  *** sf size %d ' % params.sf_size)
    elif(params.remove_stripe_method == 'none'):
        log.warning('  *** *** none')

    return data

def phase_retrieval(data, params):
    
    log.info("  *** retrieve phase")
    if (params.retrieve_phase_method == 'paganin'):
        log.info('  *** *** paganin')
        log.info("  *** *** pixel size: %s" % params.pixel_size)
        log.info("  *** *** sample detector distance: %s" % params.propagation_distance)
        log.info("  *** *** energy: %s" % params.energy)
        log.info("  *** *** alpha: %s" % params.retrieve_phase_alpha)
        data = tomopy.retrieve_phase(data,pixel_size=(params.pixel_size*1e-4),dist=(params.propagation_distance/10.0),energy=params.energy, alpha=params.retrieve_phase_alpha,pad=True)
    elif(params.retrieve_phase_method == 'none'):
        log.warning('  *** *** none')

    return data
   
def minus_log(data, params):

    log.info("  *** minus log")
    if(params.minus_log):
        log.info('  *** *** ON')
        data = tomopy.minus_log(data)
    else:
        log.warning('  *** *** OFF')

    return data

