import torch
from torch.nn import Sequential, Linear, ReLU, LeakyReLU, ModuleDict

from nff.nn.layers import GaussianSmearing
from torch import nn

nlr_dict =  {
    'ReLU': nn.ReLU(), 
    'ELU': nn.ELU(),
    'Tanh': nn.Tanh(),
    'LeakyReLU': nn.LeakyReLU(),
    'ReLU6':nn.ReLU6(),
    'SELU': nn.SELU(),
    'CELU': nn.CELU(),
    'Tanhshrink': nn.Tanhshrink()
}


LJPARAMS = {'epsilon': 1.0, 
             'sigma': 1.0}

MLPPARAMS = {'D_in': 1,
              'H': 128, 
              'num_layers': 3,
              'act': 'relu',
              'D_out': 1}

class pairMLP(torch.nn.Module):
    def __init__(self, n_gauss, r_start, r_end, n_layers, n_width, nonlinear ):
        super(pairMLP, self).__init__()
        

        nlr = nlr_dict[nonlinear]

        self.smear = GaussianSmearing(
            start=r_start,
            stop=r_end,
            n_gaussians=n_gauss,
            trainable=False
        )
        
        self.layers = nn.ModuleList(
            [
            nn.Linear(n_gauss, n_gauss),
            nlr,
            nn.Linear(n_gauss, n_width),
            nlr]
            )

        for _ in range(n_layers):
            self.layers.append(nn.Linear(n_width, n_width))
            self.layers.append(nlr)

        self.layers.append(nn.Linear(n_width, n_gauss))  
        self.layers.append(nlr)  
        self.layers.append(nn.Linear(n_gauss, 1)) 

        
    def forward(self, r):
        r = self.smear(r)
        for i in range(len(self.layers)):
            r = self.layers[i](r)
        return r


class toy2d(torch.nn.Module):
    def __init__(self):
        super(toy2d, self).__init__()
        
    def Q(self, d, r ):
        alpha = 1.942
        r0 = 0.742
        return d*( 3*torch.exp(-2*alpha*(r-r0))/2 - torch.exp(-alpha*(r-r0)) )/2
               
    def J(self, d, r ):
        alpha = 1.942
        r0 = 0.742
        return d*( torch.exp(-2*alpha*(r-r0)) - 6*torch.exp(-alpha*(r-r0)) )/4
        
    def getEnergy(self, r):  
        x=r[:, 0]
        y=r[:, 1]
        
        return (x.pow(2) + y.pow(2)).pow(2) - \
                10 * torch.exp(- 30 * (x-0.2).pow(2) - 3*(y-0.4).pow(2)) \
                - 10 * torch.exp(-30 * (x + 0.2).pow(2) - 3 * (y + 0.4).pow(2))
        
    def forward(self, xyz):
        
        if len( xyz.shape) == 1:
            xyz = xyz[None, ...]
        return self.getEnergy(xyz)
        

class leps(torch.nn.Module):
    def __init__(self):
        super(leps, self).__init__()
        
    def Q(self, d, r ):
        alpha = 1.942
        r0 = 0.742
        return d*( 3*torch.exp(-2*alpha*(r-r0))/2 - torch.exp(-alpha*(r-r0)) )/2
               
    def J(self, d, r ):
        alpha = 1.942
        r0 = 0.742
        return d*( torch.exp(-2*alpha*(r-r0)) - 6*torch.exp(-alpha*(r-r0)) )/4
        
    def getEnergy(self, r):  
        x=r[:, 0]
        y=r[:, 1]
        
        a = 0.05
        b = 0.3
        c = 0.05
        dAB = 4.746
        dBC = 4.746
        dAC = 3.445

        rAB = x
        rBC = y
        rAC = rAB + rBC

        JABred = self.J(dAB, rAB)/(1+a)
        JBCred = self.J(dBC, rBC)/(1+b)
        JACred = self.J(dAC, rAC)/(1+c)
                              
        return self.Q(dAB, rAB)/(1+a) + \
               self.Q(dBC, rBC)/(1+b) + \
               self.Q(dAC, rAC)/(1+c) - \
               torch.sqrt( JABred*JABred + \
                           JBCred*JBCred + \
                           JACred*JACred - \
                           JABred*JBCred - \
                           JBCred*JACred - \
                           JABred*JACred )
    def forward(self, xyz):
        
        if len( xyz.shape) == 1:
            xyz = xyz[None, ...]
        return self.getEnergy(xyz)

class MLP2d(torch.nn.Module):
    def __init__(self, D_in=2, H=128, D_out=1, num_layers=3, act='relu', excluded_vol=True):
        super(MLP2d, self).__init__()
        
        act_dict = {'relu': torch.nn.ReLU()}
        
        self.NN = torch.nn.ModuleList([])
        self.NN.append(torch.nn.Linear(D_in, H))
        self.NN.append(act_dict['relu'])
        for i in range(num_layers):
            self.NN.append(torch.nn.Linear(H, H))
            self.NN.append(act_dict['relu'])
        self.NN.append(torch.nn.Linear(H, 1))
        
    def forward(self, x):
        for layer in self.NN:
            x = layer(x)
        return x.squeeze()


class LennardJones(torch.nn.Module):
    def __init__(self, sigma=1.0, epsilon=1.0):
        super(LennardJones, self).__init__()
        self.sigma = torch.nn.Parameter(torch.Tensor([sigma]))
        self.epsilon = torch.nn.Parameter(torch.Tensor([epsilon]))

    def LJ(self, r, sigma, epsilon):
        return 4 * epsilon * ((sigma/r)**12 - (sigma/r)**6)

    def forward(self, x):
        return self.LJ(x, self.sigma, self.epsilon)

class LennardJones69(torch.nn.Module):
    def __init__(self, sigma=1.0, epsilon=1.0):
        super(LennardJones69, self).__init__()
        self.sigma = torch.nn.Parameter(torch.Tensor([sigma]))
        self.epsilon = torch.nn.Parameter(torch.Tensor([epsilon]))

    def LJ(self, r, sigma, epsilon):
        return 4 * epsilon * ((sigma/r)**9 - (sigma/r)**6)

    def forward(self, x):
        return self.LJ(x, self.sigma, self.epsilon)

class ExcludedVolume(torch.nn.Module):
    def __init__(self, sigma=1.0, epsilon=1.0, power=12):
        super(ExcludedVolume, self).__init__()
        self.sigma = torch.nn.Parameter(torch.Tensor([sigma]))
        self.epsilon = torch.nn.Parameter(torch.Tensor([epsilon]))
        self.power = power

    def LJ(self, r, sigma, epsilon):
        return 4 * epsilon * ((sigma/r)**self.power )

    def forward(self, x):
        return self.LJ(x, self.sigma, self.epsilon)

class Buck(torch.nn.Module):
    def __init__(self, A=1.0, B=1.0, C=1.0):
        super(Buck, self).__init__()
        self.A = torch.nn.Parameter(torch.Tensor([A]))
        self.B = torch.nn.Parameter(torch.Tensor([B]))
        self.C = torch.nn.Parameter(torch.Tensor([C]))

    def Buckingham(self, r, A, B, C):
        return A * torch.exp(- B * r) - C / r**6

    def forward(self, x):
        return self.Buckingham(x, self.A, self.B, self.C)


class MLP(torch.nn.Module):
    def __init__(self, D_in=1, H=128, D_out=1, num_layers=3, act='relu', excluded_vol=True):
        super(MLP, self).__init__()
        
        act_dict = {'relu': torch.nn.ReLU()}
        
        self.NN = torch.nn.ModuleList([])
        self.NN.append(torch.nn.Linear(D_in, H))
        self.NN.append(act_dict['relu'])
        for i in range(num_layers):
            self.NN.append(torch.nn.Linear(H, H))
            self.NN.append(act_dict['relu'])
        self.NN.append(torch.nn.Linear(H, 1))
        self.excluded_vol = excluded_vol
        
    def forward(self, x):
        if self.excluded_vol:
            u_ex =  (0.6/x) ** 12
        else:
            u_ex = 0.0 
        for layer in self.NN:
            x = layer(x)
        u_ex += x
        return u_ex

### tests 

def test(pair_dis):
    linspace = torch.linspace(0, 2.5, 100)
    pair = MLP(**MLPPARAMS).to(3)
    pair(pair_dis[..., None])