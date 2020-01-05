import os
import logging
import glob
import tempfile
import sys
import numpy as np
import tomopy
import dxchange

from tomopy_cli import config #, __version__
from tomopy_cli import log
from tomopy_cli import file_io


def tomo(params):

    # print(params)
    fname = params.hdf_file
    nsino = float(params.nsino)
    ra_fname = params.rotation_axis_file

    # print(params)

    if os.path.isfile(fname):    
        log.info("Reconstructing a single file: %s" % fname)   
        if params.reconstruction_type == "try":            
            try_center(params)
        elif params.reconstruction_type == "slice":
            rec_slice(params)
        elif params.reconstruction_type == "full":
            rec_full(params)
        else:
            log.error("Option: %s is not supported " % params.reconstruction_type)   

    elif os.path.isdir(fname):
        log.info("Reconstructing a folder containing multiple files")   

    else:
        log.error("Directory or File Name does not exist: %s" % fname)

    # update config file
    sections = config.RECON_PARAMS
    config.write(params.config, args=params, sections=sections)
    return

    fname = str(params.input_file_path)

    start = params.slice_start
    end = params.slice_end

   # Read raw data.
    if  (params.full_reconstruction == False) : 
        end = start + 1
    

#    LOG.info('Slice start/end: %s', end)

    proj, flat, dark, theta = dxchange.read_aps_32id(fname, sino=(start, end))
    # LOG.info('Slice start/end: %s, %s', start, end)
    # LOG.info('Data successfully imported: %s', fname)
    # LOG.info('Projections: %s', proj.shape)
    # LOG.info('Flat: %s', flat.shape)
    # LOG.info('Dark: %s', dark.shape)

    # Flat-field correction of raw data.
    data = tomopy.normalize(proj, flat, dark)
    # LOG.info('Normalization completed')

    data = tomopy.downsample(data, level=int(params.binning))
    # LOG.info('Binning: %s', params.binning)

    # remove stripes
    data = tomopy.remove_stripe_fw(data,level=5,wname='sym16',sigma=1,pad=True)
    # LOG.info('Ring removal completed')    

    # phase retrieval
    #data = tomopy.prep.phase.retrieve_phase(data,pixel_size=detector_pixel_size_x,dist=sample_detector_distance,energy=monochromator_energy,alpha=8e-3,pad=True)

    # Find rotation center
    #rot_center = tomopy.find_center(proj, theta, init=290, ind=0, tol=0.5)

    # Set rotation center.
    rot_center = params.center/np.power(2, float(params.binning))
    # LOG.info('Rotation center: %s', rot_center)

    data = tomopy.minus_log(data)
    # LOG.info('Minus log compled')

    # Reconstruct object using Gridrec algorithm.
    # LOG.info('Reconstruction started using %s', params.reconstruction_algorithm)
    if (str(params.reconstruction_algorithm) == 'sirt'):
        # LOG.info('Iteration: %s', params.iteration_count)
        rec = tomopy.recon(data, theta,  center=rot_center, algorithm='sirt', num_iter=params.iteration_count)
    else:
        # LOG.info('Filter: %s', params.filter)
        rec = tomopy.recon(data, theta, center=rot_center, algorithm='gridrec', filter_name=params.filter)

    # LOG.info('Reconstrion of %s completed', rec.shape)

    # Mask each reconstructed slice with a circle.
    rec = tomopy.circ_mask(rec, axis=0, ratio=0.95)

    
    if (params.dry_run == False):
         # Write data as stack of TIFs.
        fname = str(params.output_path) + 'reco'
        dxchange.write_tiff_stack(rec, fname=fname, overwrite=True)
        # LOG.info('Reconstrcution saved: %s', fname)

    if  (params.full_reconstruction == False) :
        return rec

def try_center(params):

    data_shape = file_io.get_dx_dims(params.hdf_file, 'data')

    log.info(data_shape)
    ssino = int(data_shape[1] * params.nsino)

    # downsample
    params.rotation_axis = params.rotation_axis/np.power(2, float(params.binning))
    params.center_search_width = params.center_search_width/np.power(2, float(params.binning))

    center_range = (params.rotation_axis-params.center_search_width, params.rotation_axis+params.center_search_width, 0.5)
    log.info('  *** reconstruct slice %d with rotation axis ranging from %.2f to %.2f in %.2f pixel steps' % (ssino, center_range[0], center_range[1], center_range[2]))

    # Select sinogram range to reconstruct
    start = ssino
    end = start + 1
    sino = (start, end)

    # Read APS 32-BM raw data.
    proj, flat, dark, theta = file_io.read_tomo(params, sino)

    # Flat-field correction of raw data.
    data = tomopy.normalize(proj, flat, dark, cutoff=1.4)

    # remove stripes
    data = tomopy.remove_stripe_fw(data,level=7,wname='sym16',sigma=1,pad=True)

    log.info("  *** raw data: %s" % params.hdf_file)
    log.info("  *** center: %f" % params.rotation_axis)

    data = tomopy.minus_log(data)

    data = tomopy.remove_nan(data, val=0.0)
    data = tomopy.remove_neg(data, val=0.00)
    data[np.where(data == np.inf)] = 0.00


    # downsample
    # params.rotation_axis = params.rotation_axis/np.power(2, float(params.binning))
    data = tomopy.downsample(data, level=int(params.binning))

    data_shape2 = data_shape[2]
    data_shape2 = data_shape2 / np.power(2, float(params.binning))

    stack = np.empty((len(np.arange(*center_range)), data_shape[0], int(data_shape2)))

    index = 0
    for axis in np.arange(*center_range):
        stack[index] = data[:, 0, :]
        index = index + 1

    # padding 
    N = stack.shape[2]
    stack_pad = np.zeros([stack.shape[0],stack.shape[1],3*N//2],dtype = "float32")
    stack_pad[:,:,N//4:5*N//4] = stack
    stack_pad[:,:,0:N//4] = np.reshape(stack[:,:,0],[stack.shape[0],stack.shape[1],1])
    stack_pad[:,:,5*N//4:] = np.reshape(stack[:,:,-1],[stack.shape[0],stack.shape[1],1])
    stack = stack_pad


    # Reconstruct the same slice with a range of centers. 
    rec = tomopy.recon(stack, theta, center=np.arange(*center_range)+N//4, sinogram_order=True, algorithm=params.reconstruction_algorithm, filter_name=params.filter, nchunk=1)
    rec = rec[:,N//4:5*N//4,N//4:5*N//4]
 
    # Mask each reconstructed slice with a circle.
    #rec = tomopy.circ_mask(rec, axis=0, ratio=0.95)

    index = 0
    # Save images to a temporary folder.
    # variableDict['rec_dir'] = os.path.dirname(params.hdf_file) + '_rec'
    fname = os.path.dirname(params.hdf_file) + '_rec' + os.sep + 'try_center' + os.sep + file_io.path_base_name(params.hdf_file) + os.sep + 'recon_' ##+ os.path.splitext(os.path.basename(params.hdf_file))[0]    
    for axis in np.arange(*center_range):
        rfname = fname + str('{0:.2f}'.format(axis*np.power(2, float(params.binning))) + '.tiff')
        dxchange.write_tiff(rec[index], fname=rfname, overwrite=True)
        index = index + 1
    log.info("  *** reconstructions: %s" % fname)

def rec_slice(params):
    log.info("  *** rec_slice")

def rec_full(params):
    log.info("  *** rec_full")
