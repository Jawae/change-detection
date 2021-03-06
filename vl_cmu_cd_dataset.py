import torch
from torch.utils.data import Dataset
from torchvision import transforms, datasets
from PIL import Image
import numpy as np
from skimage import io
import argparse
import matplotlib.pyplot as plt
import pickle
import time
import h5py
import glob
import os
import time
import numpy.random
import pdb
#from pdb import set_trace as st

MaskOut = [0,0,0]
NoChange = [255, 255, 255]
Barrier = [136, 0, 21]
Bin = [237, 28, 36]
ConstructionMaintenance = [255, 127, 39]
Misc = [255, 242, 0] # this class is a mistake, only one train example, and it's actually Rubbish class...
OtherObjects = [34, 177, 76] 
PersonCycle = [0, 162, 232]
Rubbish = [63, 72, 204]
Sign = [163, 73, 164]
TrafficCone = [255, 174, 201]
Vehicle = [181, 230, 29]

CLASS_DICT = np.array([NoChange, Barrier, Bin, ConstructionMaintenance,
                          OtherObjects, PersonCycle, Rubbish, Sign, TrafficCone, Vehicle])
CHANGE_CLASSES = ["NoChange", "Barrier", "Bin", "ConstructionMaintenance",
                          "OtherObjects", "PersonCycle", "Rubbish", "Sign", "TrafficCone", "Vehicle"]

''' Returns 224 x 224 x 11 vector '''
def oldprepareGTData(mask, num_class = 10):
    new_mask = np.zeros(mask.shape[0:2] + (num_class,), dtype=np.float32)
    # Mask Out Class
    new_mask[np.all(mask == np.zeros((1,1,3), dtype=np.int32) , axis=2),0] = 1
    # All other classes
    for i in range(num_class):
        new_mask[np.all(mask == CLASS_DICT[i].reshape(1,1,3) , axis=2),i] = 1
    
    return new_mask


''' Returns 224 x 224 x 1 vector '''
def prepareGTData(mask, num_class = 10):
    #pdb.set_trace()
    mask = mask.astype('int')
    new_mask = np.zeros(mask.shape[0:2], dtype=np.int64)
    # Mask Out Class
    new_mask[np.all(mask == np.zeros((1,1,3), dtype=np.int32) , axis=2)] = np.int64(-1)
    new_mask[np.all(mask == np.array(Misc, dtype=np.int32).reshape(1,1,3) , axis=2)] = np.int64(4)
    #OtherObjects
    # All other classes
    for i in range(num_class):
        new_mask[np.all(mask == CLASS_DICT[i].reshape(1,1,3) , axis=2)] = np.int64(i)
    
    return new_mask

class VLCMUCDDataset(Dataset):
    ''''
    Dataset Class for VL-CMU-CD Dataset
    '''
    def __init__(self, file_paths,  training=False, probability=0.5):
        with open(file_paths, "rb") as fp:
            self.vlcmu_data = pickle.load(fp)
        self.resize_image = transforms.Compose([
            transforms.ToPILImage(), 
            transforms.Resize((224,224)),
        ])
        self.max_rot = 15
        self.max_trans = 0.2
        self.max_scale_diff = 0.2
        self.max_shear_deg = 10

        self.training = training
        self.p = probability
        self.normalize_transform = transforms.Normalize(mean=[0.485, 0.456, 0.406],
                             std=[0.229, 0.224, 0.225])

    def __len__(self):
        return len(self.vlcmu_data['gt'])

    def __getitem__(self, idx):
        im1 = io.imread(self.vlcmu_data['im1'][idx])
        im2 = io.imread(self.vlcmu_data['im2'][idx])
        gt = io.imread(self.vlcmu_data['gt'][idx])

        # print(self.vlcmu_data['im1'][idx])
        # print(self.vlcmu_data['im2'][idx])
        # print(self.vlcmu_data['gt'][idx])
        im1 = self.resize_image(im1).convert('RGB')
        im2 = self.resize_image(im2).convert('RGB')
        gt = self.resize_image(gt).convert('RGB')

        if self.training:
            # Shear
            if (np.random.rand() < self.p):
                angle = int( self.max_rot * np.random.rand() )
                translation = (self.max_trans * np.random.rand() , self.max_trans * np.random.rand() )
                scale = self.max_scale_diff * 2. * (np.random.rand() - 0.5) + 1.
                shear = int( self.max_shear_deg * np.random.rand() )
                
                im1 = transforms.functional.affine(im1, angle=angle, translate=translation, 
                                                   scale=scale, shear=shear, resample=Image.NEAREST, fillcolor=None)
                im2 = transforms.functional.affine(im2, angle=angle, translate=translation, 
                                                   scale=scale, shear=shear, resample=Image.NEAREST, fillcolor=None)
                gt = transforms.functional.affine(gt, angle=angle, translate=translation, 
                                                   scale=scale, shear=shear, resample=Image.NEAREST, fillcolor=None)
            if (np.random.rand() < self.p):
                im1 = transforms.functional.hflip(im1)
                im2 = transforms.functional.hflip(im2)
                gt = transforms.functional.hflip(gt)

            


        im1 = self.normalize_transform( transforms.ToTensor()(im1).float() )
        im2 = self.normalize_transform( transforms.ToTensor()(im2).float() )
        # Swap randomly
        if self.training and np.random.rand() < 0.5:
            im2,im1 = im1,im2

        gt_orig = transforms.ToTensor()(gt)
        gt = prepareGTData( np.moveaxis(gt_orig.numpy()*255, 0, -1))
        gt = transforms.ToTensor()(gt).long()
        if self.training and np.random.rand() < 0.15:
            im2 = im1
            gt = torch.zeros_like(gt, dtype=torch.long)
        return {  'im1': im1, 'im2':im2, 'gt': gt , 'gt_orig' : gt_orig }

def parse_args():
    parser = argparse.ArgumentParser(description='Dataset Loader for PyTorch Networks')
    parser.add_argument('--train_file_path', type=str, default='./train/train.txt')
    return parser.parse_args()

def visualizeImages(im1,im2,gt):
    mean = torch.from_numpy(np.array([0.485, 0.456, 0.406]).reshape(3,1,1)).float()
    std = torch.from_numpy(np.array([0.229, 0.224, 0.225]).reshape(3,1,1)).float()
    transform = transforms.ToPILImage()
    
    c, h, w = im1.shape
    combined = np.zeros((c, h, w*3))
    combined[:,:, :w] = std*im1 + mean
    combined[:,:, w:2*w] = std*im2 + mean
    combined[:,:, 2*w:] = gt
    combined = transform(torch.from_numpy(combined).float())
    # im1 = transform(std*im1 + mean)
    # im2 = transform(std*im2 + mean)
    return combined

def visualizeAllImages(im1,im2,gt, mask):
    mean = torch.from_numpy(np.array([0.485, 0.456, 0.406]).reshape(3,1,1)).float()
    std = torch.from_numpy(np.array([0.229, 0.224, 0.225]).reshape(3,1,1)).float()
    transform = transforms.ToPILImage()
    
    c, h, w = im1.shape
    combined = np.zeros((c, h, w*4))
    combined[:,:, :w] = std*im1 + mean
    combined[:,:, w:2*w] = std*im2 + mean
    combined[:,:, 2*w:3*w] = gt
    combined[:,:, 3*w:] = mask
    combined = transform(torch.from_numpy(combined).float())
    # im1 = transform(std*im1 + mean)
    # im2 = transform(std*im2 + mean)
    return combined

def visualizeMaskedImages(im1,im2,gt, mask):
    mean = torch.from_numpy(np.array([0.485, 0.456, 0.406]).reshape(3,1,1)).float()
    std = torch.from_numpy(np.array([0.229, 0.224, 0.225]).reshape(3,1,1)).float()
    transform = transforms.ToPILImage()
    bin_mask = mask == 1 # no-change is (1,1,1) 
    bin_mask = bin_mask.double()
    alpha = 0.4
    beta = (1.0 - alpha)
    c, h, w = im1.shape
    combined = np.zeros((c, h, w*4))
    combined[:,:, :w] = std*im1 + mean
    combined[:,:, w:2*w] = std*im2 + mean
    combined[:,:, 2*w:3*w] = gt
    combined[:,:, 3*w:] = combined[:,:, w:2*w]*bin_mask + (1-bin_mask)*(alpha*combined[:,:, w:2*w] + beta*(mask) )
    combined = transform(torch.from_numpy(combined).float())
    # im1 = transform(std*im1 + mean)
    # im2 = transform(std*im2 + mean)
    return combined

def visualizeOneImage(im1):
    mean = torch.from_numpy(np.array([0.485, 0.456, 0.406]).reshape(3,1,1)).float()
    std = torch.from_numpy(np.array([0.229, 0.224, 0.225]).reshape(3,1,1)).float()
    transform = transforms.ToPILImage()
    im1 = transform(std*im1 + mean)
    return im1

def labelVisualize(img, num_class=10, target_size = (224,224)):
    #img = (img.reshape( num_class, target_size[0], target_size[1]) ).argmax( axis=0 )
    seg_img = np.zeros( ( target_size[0], target_size[1], 3 ) ).astype('uint8')
    for c in range(num_class):
        seg_img[:,:,0] += ( (img[:,: ] == c )*( CLASS_DICT[c][0] )).astype('uint8')
        seg_img[:,:,1] += ((img[:,: ] == c )*( CLASS_DICT[c][1] )).astype('uint8')
        seg_img[:,:,2] += ((img[:,: ] == c )*( CLASS_DICT[c][2] )).astype('uint8')
    #seg_img = io.transform.resize(seg_img  , (768, 1024 ))
    #skio.imsave(  "output/output" + str(imNumber) + ".png" , seg_img )
    return seg_img

def main(args):
    

    vlcmu = VLCMUCDDataset(args.train_file_path, training=True, probability=0.5)
    for idx in range(len(vlcmu)):
        print(idx)
        data = vlcmu[idx]
        # print(data['gt'].shape)
        # plt.imshow(visualizeImages(data['im1'],data['im2'],data['gt_orig']))
        edges = data['edges']
        plt.imshow(edges)
        plt.draw()
        plt.pause(0.3)


if __name__ == '__main__':
    args = parse_args()
    main(args)