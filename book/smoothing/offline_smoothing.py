#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Illustrates the different off-line particle smoothing algorithms using the
bootstrap filter of the following model:

X_t|X_{t-1}=x_{t-1} ~ N(mu+phi(x_{t-1}-mu),sigma^2)
Y_t|X_t=x_t ~ Poisson(exp(x_t))
as in first example in Chopin and Singh (2014, Bernoulli)

More precisely, we compare different smoothing algorithms for approximating
the smoothing expectation of additive function psit, defined as 
sum_{t=0}^{T-2} \psi_t(X_t, X_{t+1})
see below for a definition of psi_t 

See also Chapter 11 of the book; in particular the box-plots of Figure 11.4 
and Figure 11.5 were generated by this script. 

Warning: takes about 4-5hrs to complete (if run on a single core). 
"""

from __future__ import division, print_function

from matplotlib import pyplot as plt
from matplotlib import rc  # tex
import numpy as np
from scipy import stats
import seaborn as sb  # box-plots

from particles import utils
from particles.smoothing import smoothing_worker
from particles import state_space_models as ssms

# considered class of models

class DiscreteCox_with_add_f(ssms.DiscreteCox):
    """ A discrete Cox model:
    Y_t ~ Poisson(e^{X_t})
    X_t - mu = phi(X_{t-1}-mu)+U_t,   U_t ~ N(0,1)
    X_0 ~ N(mu,sigma^2/(1-phi**2))
    """
    def upper_bound_log_pt(self, t):
        return -0.5 * np.log(2 * np.pi * self.sigma**2)

# set up model, simulate data
T = 100
mu0 = 0. 
phi0 = .9
sigma0 = .5  # true parameters
my_ssm = DiscreteCox_with_add_f(mu=mu0, phi=phi0, sigma=sigma0)
_, data = my_ssm.simulate(T)

# Aim is to compute the smoothing expectation of
# sum_{t=0}^{T-2} \psi(t, X_t, X_{t+1})
# here, this is the score at theta=theta_0


def psi0(x):
    return -0.5 / sigma0**2 + (0.5 * (1. - phi0**2) / sigma0**4) * (x - mu0)**2


def psit(t, x, xf):
    """ A function of t, X_t and X_{t+1} (f=future) """
    if t == 0:
        return psi0(x) + psit(1, x, xf)
    else:
        return -0.5 / sigma0**2 + (0.5 / sigma0**4) * ((xf - mu0) - 
                                                       phi0 * (x - mu0))**2

# FK models
fkmod = ssms.Bootstrap(ssm=my_ssm, data=data)
# FK model for information filter: same model with data in reverse
fk_info = ssms.Bootstrap(ssm=my_ssm, data=data[::-1])

# logpdf of gamma_{t}(dx_t), the 'prior' of the information filter
def log_gamma(x):
    return stats.norm.logpdf(x, loc=mu0,
                             scale=sigma0 / np.sqrt(1. - phi0**2))

Ns = [100, 400, 1600, 6400]  # , 25600]#, 102400]#, 409600, 1638400]
methods = ['FFBS_ON', 'FFBS_ON2', 'two-filter_ON',
           'two-filter_ON_prop', 'two-filter_ON2']

results = utils.multiplexer(f=smoothing_worker, method=methods, N=Ns, 
                                  fk=fkmod, fk_info=fk_info, add_func=psit,
                                  log_gamma=log_gamma, nprocs=0, nruns=10)

# Plots
# =====
savefigs = False  # change this to save the plots as PDFs
plt.style.use('ggplot')
palette = sb.dark_palette("lightgray", n_colors=5, reverse=False)
sb.set_palette(palette)
rc('text', usetex=True)  # latex

ON = r'$\mathcal{O}(N)$'
ON2 = r'$\mathcal{O}(N^2)$'
pretty_names = {}
pretty_names['FFBS_ON'] = ON + r' FFBS'
pretty_names['FFBS_ON2'] = ON2 + r' FFBS'
pretty_names['two-filter_ON'] = ON + r' two-filter, basic proposal'
pretty_names['two-filter_ON2'] = ON2 + r' two-filter'
pretty_names['two-filter_ON_prop'] = ON + r' two-filter, better proposal'

# box-plot of est. errors vs N and method (Figure 11.4)
plt.figure()
plt.xlabel(r'$N$')
plt.ylabel('smoothing estimate')
sb.boxplot(y=[np.mean(r['est']) for r in results],
           x=[r['N'] for r in results],
           hue=[pretty_names[r['method']] for r in results],
           palette=palette,
           flierprops={'marker': 'o',
                       'markersize': 4,
                       'markerfacecolor': 'k'})
if savefigs:
    plt.savefig('offline_boxplots_est_vs_N.pdf')

# CPU times as a function of N (Figure 11.5)
plt.figure()
plt.xscale('log')
plt.yscale('log')
plt.xlabel(r'$N$')
# both O(N^2) algorithms have the same CPU cost, so we plot only
# one line for both
pretty_names['FFBS_ON2'] += " and " + pretty_names['two-filter_ON2']
for method in ['FFBS_ON2', 'FFBS_ON',
               'two-filter_ON_prop', 'two-filter_ON']:
    ls = '-' if method=='FFBS_ON2' else '--'
    plt.plot(Ns, [np.mean(np.array([r['cpu'] for r in results
                              if r['method'] == method and r['N'] == N]))
                  for N in Ns], label=pretty_names[method],
             linewidth=3, ls=ls)
plt.ylabel('cpu time (s)')
plt.legend(loc=2)
if savefigs:
    plt.savefig('offline_cpu_vs_N.pdf')

# and finally
plt.show()
