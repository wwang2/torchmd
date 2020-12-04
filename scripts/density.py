import os
import numpy as np
import matplotlib.pyplot as plt
import sys 

import torch
from torch.optim import Adam
from torchmd.sovlers import odeint_adjoint as  odeint
from nglview import show_ase, show_file, show_mdtraj

from nff.nn.layers import GaussianSmearing
from ase import Atoms
from math import sqrt

from torchmd.sampler import NH_sampler, eq_NN, Noneq_NN

from sklearn.datasets import make_circles, make_checkerboard, make_moons

import math

def plot_pes(model, Xdata, ref, t, device, fname=None):
    
    #plt.title('lr={} beta={} acc={}'.format(lr, beta, acc))
    plt.figure(figsize=(7,5))
    res=30
    xlist = np.linspace(-2., 2., res)
    ylist = np.linspace(-2., 2., res)
    X_mesh, Y_mesh = np.meshgrid(xlist, ylist)
    data = torch.Tensor(np.concatenate((X_mesh[:,:, None],Y_mesh[:,:,None]), axis=2).reshape(-1,2)).to(device)

    # take final time step
    final_t = torch.Tensor([t] * data.shape[0]).to(device)

    output = model(data, final_t.reshape(-1, 1)).detach().cpu().numpy().reshape(res, res)
    cp = plt.contourf(X_mesh, Y_mesh, output, 40,# cmap='Blues',
                      alpha=0.4)
    
    Xdata = Xdata.detach().cpu().numpy()

    ref = ref#.detach().cpu().numpy()
    plt.scatter(Xdata[::,0] , Xdata[::,1], alpha=0.8, s=4)
    plt.scatter(ref[::,0] , ref[::,1], alpha=0.3, s=4)
    plt.xlim((-2, 2))
    plt.ylim((-2, 2))
    plt.colorbar(cp)
    if fname:
        plt.savefig(fname, bbox_inches='tight')
    plt.show()


def train_ebm(params, model_path):

    if not os.path.exists(model_path):
        os.makedirs(model_path)

    time_dependent = params['time_dependent']
    DEVICE = params['DEVICE'] 
    num_chains = params['num_chains']= 3
    B = params['B'] = 4096
    tau = params['tau']
    dt = params['dt']
    dim = params['dim']
    p_targ = params['p_targ']
    t_len = int( tau / dt )

    h = Noneq_NN(tau=tau, device=DEVICE, k_0=1.0).to(DEVICE)

    f_x = NH_sampler(h, 
                torch.Tensor([1.0]), 
                ttime=50.0, 
                num_chains=num_chains, 
                device=DEVICE,
                target_momentum=p_targ,
                time_dependent=time_dependent,
                
                dim=2).to(DEVICE)

    optimizer = torch.optim.Adam(list( h.parameters() ), lr=5e-4)

    loss_run = []

    for epoch in range(5000):
        
        B_sampled = 128

        final_t = torch.Tensor([tau] * B_sampled).to(DEVICE)
        t_0 = torch.Tensor([0.0] * B_sampled).to(DEVICE)
        
        # get samples from data 
        sample_batch, _= make_circles(n_samples=B_sampled, noise=0.1, factor=0.5)
        p_v = torch.empty(B_sampled, 3).normal_(mean=0,std=1)
        q = torch.Tensor(sample_batch) # torch.empty(B_sampled, 2).normal_(mean=0,std=0.5) 
        p = torch.empty(B_sampled, 2).normal_(mean=0,std=p_targ)
        W = torch.zeros(B_sampled, 1).to(DEVICE)
        Q = torch.zeros(B_sampled, 1).to(DEVICE)

        pq = torch.cat((p, q, p_v), dim=1).to(DEVICE)
        pq.requires_grad= True

        t = torch.Tensor([dt * i for i in range(t_len)]).to(DEVICE)
        
        if time_dependent:
            x, W_traj, Q_traj = odeint(f_x, (pq, W, Q), t, method='rk4')
            # logZ = -torch.log( torch.exp(-W_traj[-1].reshape(-1)).mean() )
            # loss = -logZ + data_nll.mean()  + 0.05 * ( (data_nll).pow(2).mean() + (sample_nll).pow(2).mean() )  \
            #         + 0.05 * (W_traj[-1]).pow(2).mean()

            # minimize log likelihood first 

            #import ipdb; ipdb.set_trace()

            logp = -h(x[-1, :, dim: dim*2], final_t) - torch.log( torch.exp(-W_traj[-1].reshape(-1)).mean() )

            # sample nll
            nll_z = 0.5 * x[-1, :, dim: dim*2].pow(2).add(math.log(2 * math.pi)).sum(1)
            #print(x[-1].shape)
            
            d_logp = nll_z  + logp

            loss = d_logp.mean()



        else:       
            x = odeint(f_x, pq, t, method='rk4')
            sample_nll = h(x[10:][::5, :, 2:4].reshape(-1, 2), final_t)
            logZ = -torch.log(torch.exp(-sample_nll.squeeze() ).mean() )  
            loss = data_nll.mean() -logZ

        loss.backward()
        #loss_run.append([data_nll.mean().item(), -logZ.item()]) 

        optimizer.step()
        optimizer.zero_grad()
        
        print(loss.item())

        if epoch % 10 == 0:
            plot_pes(h, 
                     x[-1, ::, dim: dim*2].reshape(-1, dim), 
                     sample_batch[::], 
                     0.0, 
                     device=DEVICE,
                     fname=model_path + "{}.png".format(epoch))

    return loss.item()


params = {}

params['time_dependent'] = True
params['DEVICE'] = 1
params['num_chains']= 3
params['B'] = 4096
params['tau'] = 5.0
params['dt'] = 0.1
params['dim'] = 2
params['p_targ'] = 1.0

model_path = 'noneq_1105_2/'

train_ebm(params, model_path)