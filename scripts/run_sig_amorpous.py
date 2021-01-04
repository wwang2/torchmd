
import argparse
from sigopt import Connection
from fit_rdf_gnn import *

parser = argparse.ArgumentParser()
parser.add_argument("-logdir", type=str)
parser.add_argument("-device", type=int, default=0)
parser.add_argument("-id", type=int, default=None)
parser.add_argument("-data", type=str, nargs='+')
parser.add_argument("-val", type=str, nargs='+')
parser.add_argument("-size", type=int, default=4)
parser.add_argument("--dry_run", action='store_true', default=False)
parser.add_argument("--pair", action='store_true', default=False)
parser.add_argument("--anneal", action='store_true', default=False)
params = vars(parser.parse_args())


print(params['data'])

if params['dry_run']:
    token = 'FSDXBSGDUZUQEDGDCYPCXFTRXFNYBVXVACKZQUWNSOKGKGFN'
    n_obs = 2
    tmax = 200
    n_epochs = 2
    n_sim = 2
else:
    token = 'RXGPHWIUAMLHCDJCDBXEWRAUGGNEFECMOFITCRHCEOBRMGJU'
    n_obs = 1000
    tmax = 25000
    n_epochs = 1000
    n_sim = 50

logdir = params['logdir']

#Intiailize connections 
conn = Connection(client_token=token)


if params['pair']:

    parameters = [
            dict(name='n_width', type='int', bounds=dict(min=32, max=128)),
            dict(name='n_layers', type='int', bounds=dict(min=0, max=4)),
            dict(name='nonlinear', type='categorical', categorical_values=['ReLU', 'ELU', 'Tanh', 
                                                                            'LeakyReLU', 'ReLU6', 
                                                                            'SELU', 'CELU', 'Tanhshrink']),
            dict(name='gaussian_width', type='double', bounds=dict(min=0.05, max=0.25)),
            dict(name='power', type='int', bounds=dict(min=6, max=12)),
            dict(name='sigma', type='double', bounds=dict(min=1.0, max=1.5)),
            dict(name='epsilon', type='double', bounds=dict(min=0.0025, max=0.025)),
            dict(name='opt_freq', type='int', bounds=dict(min=10, max=80)),
            dict(name='lr', type='double', bounds=dict(min=1.1e-7, max=5e-4)),
            dict(name='cutoff', type='double', bounds=dict(min=3.0, max=4.0)),
            dict(name='mse_weight', type='double', bounds=dict(min=0.0, max=1.0)),
            dict(name='nbins', type='int', bounds=dict(min=32, max=128)),
        ]

else:
    parameters = [
            dict(name='n_atom_basis', type='categorical',categorical_values=["tiny", "low", "mid", "high"]),
            dict(name='n_filters', type='categorical', categorical_values=["tiny", "low", "mid", "high"]),
            dict(name='gaussian_width', type='double', bounds=dict(min=0.05, max=0.25)),
            dict(name='n_convolutions', type='int', bounds=dict(min=1, max=5)),
            dict(name='sigma', type='double', bounds=dict(min=1.0, max=1.5)),
            dict(name='epsilon', type='double', bounds=dict(min=0.0025, max=0.025)),
            dict(name='opt_freq', type='int', bounds=dict(min=10, max=80)),
            dict(name='lr', type='double', bounds=dict(min=1.1e-7, max=5e-4)),
            dict(name='cutoff', type='double', bounds=dict(min=3.0, max=4.0)),
            dict(name='mse_weight', type='double', bounds=dict(min=0.0, max=1.0)),
            dict(name='nbins', type='int', bounds=dict(min=32, max=128)),
        ]

if params['anneal']:
    parameters += [
            dict(name='start_T', type='double', bounds=dict(min=300, max=500)),
            dict(name='anneal_rate', type='double', bounds=dict(min=3, max=10)),
            dict(name='anneal_freq', type='int', bounds=dict(min=1, max=20))
            ]


if params['id'] == None:
    experiment = conn.experiments().create(
        name=logdir,
        metrics=[dict(name='loss', objective='minimize')],
        parameters=parameters,
        observation_budget = n_obs, # how many iterations to run for the optimization
        parallel_bandwidth=10,
    )

elif type(params['id']) == int:
    experiment = conn.experiments(params['id']).fetch()


i = 0
while experiment.progress.observation_count < experiment.observation_budget:

    suggestion = conn.experiments(experiment.id).suggestions().create()

    sys_params = {
    'size': params['size'],
    'dt': 1.0,
    'n_epochs': n_epochs,
    'n_sim': n_sim,
    'data': params['data'],
    'val': params['val'],
    'anneal_flag': params['anneal'],
    'pair_flag': params['pair']
    }

    value = fit_rdf(assignments=suggestion.assignments, 
                            i=i, 
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