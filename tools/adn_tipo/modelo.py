"""CNN pequeña: embedding de fuente y regresión de tamaño/Lab."""
from __future__ import annotations
from pathlib import Path
import numpy as np
from PIL import Image
import torch
from torch import nn
from comun import leer, sha256

def cargar_imagen(root, fila):
    path = (Path(root) / fila['archivo']).resolve()
    if Path(root).resolve() not in path.parents or sha256(path) != fila['sha256']:
        raise ValueError('Ruta o SHA de imagen inválido')
    with Image.open(path) as im:
        return im.convert('RGB').copy()

def geometria(im):
    a=np.asarray(im.convert('RGB'),dtype=float)
    papel=np.percentile(a.reshape(-1,3),90,axis=0)
    contraste=np.linalg.norm(a-papel,axis=2)
    mask=contraste>max(20,float(contraste.max())*.3)
    yy,xx=np.where(mask)
    if not len(xx): return np.zeros(1024,np.float32),0,[0.,0.,0.]
    crop=Image.fromarray((255*(1-mask.astype(float))).astype('uint8')).crop((xx.min(),yy.min(),xx.max()+1,yy.max()+1))
    shape=np.asarray(crop.resize((32,32),Image.Resampling.BILINEAR),dtype=np.float32).ravel()/255
    # Mediana del núcleo oscuro; el papel no entra en la tinta.
    ink=np.median(a[contraste>max(20,float(contraste.max())*.75)],axis=0)
    from comun import lab
    return shape,float(yy.max()-yy.min()+1),lab(ink)

def tensor(im):
    return torch.from_numpy(np.asarray(im.resize((64,64)),dtype=np.float32).transpose(2,0,1).copy()/255)

class TipoNet(nn.Module):
    def __init__(self, clases):
        super().__init__()
        self.conv=nn.Sequential(nn.Conv2d(3,16,5,padding=2),nn.ReLU(),nn.MaxPool2d(2),
            nn.Conv2d(16,32,3,padding=1),nn.ReLU(),nn.MaxPool2d(2),
            nn.Conv2d(32,48,3,padding=1),nn.ReLU(),nn.AdaptiveAvgPool2d((4,4)))
        self.oculta=nn.Sequential(nn.Flatten(),nn.Linear(48*4*4,64),nn.ReLU())
        self.embedding=nn.Linear(64,32)
        self.clasificar=nn.Linear(32,clases)
        self.regresion=nn.Linear(64,4)
        with torch.no_grad(): self.regresion.bias.copy_(torch.tensor([1.,.4,0.,0.]))
    def forward(self,x):
        h=self.oculta(self.conv(x))
        e=nn.functional.normalize(self.embedding(h),dim=1)
        return e,self.clasificar(e),self.regresion(h)

def cargar_pesos(path, device='cpu'):
    checkpoint=torch.load(path,map_location=device,weights_only=True)
    net=TipoNet(len(checkpoint['familias'])).to(device)
    net.load_state_dict(checkpoint['state']); net.eval()
    return net,checkpoint

def prediccion_red(net,im,device='cpu'):
    with torch.inference_mode():
        e,_,r=net(tensor(im)[None].to(device))
    values=r[0].cpu().numpy()
    return e[0].cpu().numpy(),float(max(0,values[0]*24)),(values[1:]*[100,128,128]).tolist()
