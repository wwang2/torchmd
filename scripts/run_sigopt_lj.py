
import argparse
from sigopt import Connection
from gnn_fit_lj import *

parser = argparse.ArgumentParser()
parser.add_argument("-logdir", type=str)
parser.add_argument("-device", type=int, default=0)
parser.add_argument("-id", type=int, default=None)
parser.add_argument("--dry_run", action='store_true', default=False)
params = vars(parser.parse_args())

if params['dry_run']:
    token = 'FSDXBSGDUZUQEDGDCYPCXFTRXFNYBVXVACKZQUWNSOKGKGFN'
    n_obs = 2
    n_epochs = 4
    n_sim = 2
else:
    token = 'RXGPHWIUAMLHCDJCDBXEWRAUGGNEFECMOFITCRHCEOBRMGJU'
    n_obs = 1000
    n_epochs = 1000
    n_sim = 50

logdir = params['logdir']

#Intiailize connections 
conn = Connection(client_token=token)

if params['id'] == None:
    experiment = conn.experiments().create(
        name=logdir,
        metrics=[dict(name='loss', objective='minimize')],
        parameters=[
            dict(name='n_atom_basis', type='categorical',categorical_values=["tiny", "low", "mid", "high"]),
            dict(name='n_filters', type='categorical', categorical_values=["tiny", "low", "mid", "high"]),
            dict(name='gaussian_width', type='double', bounds=dict(min=0.05, max=0.25)),
            dict(name='n_convolutions', type='int', bounds=dict(min=1, max=3)),
            # dict(name='sigma', type='double', bounds=dict(min=1.1, max=2.25)),
            # dict(name='epsilon', type='double', bounds=dict(min=0.0025, max=0.025)),
            dict(name='opt_freq', type='int', bounds=dict(min=40, max=70)),
            dict(name='lr', type='double', bounds=dict(min=1.1e-5, max=5e-3)),
            dict(name='cutoff', type='double', bounds=dict(min=1.1, max=2.0)),
            dict(name='rdf_weight', type='double', bounds=dict(min=0.1, max=1.0)),
            dict(name='vacf_weight', type='double', bounds=dict(min=0.1, max=1.0)),
            dict(name='rdf_start', type='double', bounds=dict(min=0.1, max=0.8)),
            dict(name='nbins', type='int', bounds=dict(min=32, max=128)),
        ],
        observation_budget = n_obs, # how many iterations to run for the optimization
        parallel_bandwidth=10,
    )

elif type(params['id']) == int:
    experiment = conn.experiments(params['id']).fetch()

i = 0
while experiment.progress.observation_count < experiment.observation_budget:

    suggestion = conn.experiments(experiment.id).suggestions().create()

    sys_params = {
    'dt': 0.01,
    'n_epochs': n_epochs,
    'n_sim': n_sim,
    }

    value = fit_lj(assignments=suggestion.assignments, 
                            #i=i, 
                            suggestion_id=suggestion.id, 
                            device=params['device'],
                            sys_params=sys_params,
                            project_name=logdir)

    print(value)

    conn.experiments(experiment.id).observations().create(
      suggestion=suggestion.id,
      value=value,
    )

    experiment = conn.experiments(experiment.id).fetch()