#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Feb  6 14:17:28 2018

@author: Harshvardhan Gazula
@notes : Contains a variant of the single-shot regression proposed by Rogers.
         Drop site specific columns at each site and use global_beta_vector
         to calculate SSE at each local site.
"""

import os
import shelve
import numpy as np
import pandas as pd
import scipy as sp
from numba import jit, prange
from mcic_load_data import load_data


@jit(nopython=True)
def multishot_exact(X1, site_01_y1, X2, site_02_y1, X3, site_03_y1, X4,
                    site_04_y1):

    size_y = site_01_y1.shape[1]

    params = np.zeros((X1.shape[1], size_y))
    sse = np.zeros(size_y)
    tvalues = np.zeros((X1.shape[1], size_y))
    rsquared = np.zeros(size_y)

    for voxel in prange(size_y):
        print(voxel)
        y1 = site_01_y1[:, voxel]
        y2 = site_02_y1[:, voxel]
        y3 = site_03_y1[:, voxel]
        y4 = site_04_y1[:, voxel]

        # PART 01 - Calculate X'X at each local site
        cov1 = X1.T @ X1
        cov2 = X2.T @ X2
        cov3 = X3.T @ X3
        cov4 = X4.T @ X4

        Xy1 = X1.T @ y1
        Xy2 = X2.T @ y2
        Xy3 = X3.T @ y3
        Xy4 = X4.T @ y4

        # PART 02 - At the remote site
        avg_beta_vector = (np.linalg.inv(cov1 + cov2 + cov3 + cov4) @ Xy1) + (
            np.linalg.inv(cov1 + cov2 + cov3 + cov4) @ Xy2) + (
                np.linalg.inv(cov1 + cov2 + cov3 + cov4) @ Xy3) + (
                    np.linalg.inv(cov1 + cov2 + cov3 + cov4) @ Xy4)

        params[:, voxel] = avg_beta_vector

        # PART 02 - Aggregating parameter values at the remote
        count_y_local = np.array([len(y1), len(y2), len(y3), len(y4)])

        # PART 03 - SSE at each local site
        y1_estimate = np.dot(avg_beta_vector, X1.T)
        y2_estimate = np.dot(avg_beta_vector, X2.T)
        y3_estimate = np.dot(avg_beta_vector, X3.T)
        y4_estimate = np.dot(avg_beta_vector, X4.T)

        sse1 = np.linalg.norm(y1 - y1_estimate)**2
        sse2 = np.linalg.norm(y2 - y2_estimate)**2
        sse3 = np.linalg.norm(y3 - y3_estimate)**2
        sse4 = np.linalg.norm(y4 - y4_estimate)**2

        # At Local
        mean_y_local = np.array(
            [np.mean(y1), np.mean(y2),
             np.mean(y3), np.mean(y4)])

        # At Remote
        mean_y_global = np.sum(
            mean_y_local * count_y_local) / np.sum(count_y_local)

        # At Local
        sst1 = np.sum(np.square(y1 - mean_y_global))
        sst2 = np.sum(np.square(y2 - mean_y_global))
        sst3 = np.sum(np.square(y3 - mean_y_global))
        sst4 = np.sum(np.square(y4 - mean_y_global))

        # PART 05 - Finding rsquared (global)
        SSE_global = sse1 + sse2 + sse3 + sse4
        sse[voxel] = SSE_global
        SST_global = sst1 + sst2 + sst3 + sst4
        r_squared_global = 1 - (SSE_global / SST_global)
        rsquared[voxel] = r_squared_global

        # PART 04 - Finding p-value at the Remote
        varX_matrix_global = cov1 + cov2 + cov3 + cov4
        dof_global = np.sum(count_y_local) - len(avg_beta_vector)

        MSE = SSE_global / dof_global
        var_covar_beta_global = MSE * np.linalg.inv(varX_matrix_global)
        se_beta_global = np.sqrt(np.diag(var_covar_beta_global))
        ts_global = avg_beta_vector / se_beta_global

        tvalues[:, voxel] = ts_global

    return (params, sse, tvalues, rsquared, dof_global)


folder_index = input('Enter the name of the folder to save results: ')
folder_name = folder_index.replace(' ', '_')
if not os.path.exists(folder_name):
    os.makedirs(folder_name)

X1, site_01_y1, X2, site_02_y1, X3, site_03_y1, X4, site_04_y1, column_name_list = load_data(
)

(params, sse, tvalues, rsquared, dof_global) = multishot_exact(
    X1, site_01_y1, X2, site_02_y1, X3, site_03_y1, X4, site_04_y1)

ps_global = 2 * sp.stats.t.sf(np.abs(tvalues), dof_global)
pvalues = pd.DataFrame(ps_global.transpose(), columns=column_name_list)
sse = pd.DataFrame(sse.transpose(), columns=['sse'])
params = pd.DataFrame(params.transpose(), columns=column_name_list)
tvalues = pd.DataFrame(tvalues.transpose(), columns=column_name_list)
rsquared = pd.DataFrame(rsquared.transpose(), columns=['rsquared_adj'])

# %% Writing to a file
print('Writing data to a shelve file')
results = shelve.open(
    os.path.join(folder_name, 'multishotExact_results'))
results['params'] = params
results['sse'] = sse
results['pvalues'] = pvalues
results['tvalues'] = tvalues
results['rsquared'] = rsquared
results.close()
