# -*- coding: utf-8 -*-  

"""
Created on 2023/12/5

@author: Ruoyu Chen
"""

import os
# os.environ["CUDA_VISIBLE_DEVICES"] = "0"
import argparse

import numpy as np
import cv2
import math
from matplotlib import pyplot as plt
from tqdm import tqdm

from segment_anything import SamAutomaticMaskGenerator, sam_model_registry

from utils import *

def parse_args():
    parser = argparse.ArgumentParser(description='Segment Anything')
    parser.add_argument('--image-dir', 
                        type=str, 
                        default='./datasets/imagenet/ILSVRC2012_img_val',
                        help='')
    parser.add_argument('--image-file', 
                        type=str, 
                        default='./datasets/imagenet/val_languagebind_5k_true.txt',
                        help='')
    parser.add_argument('--save-dir', 
                        type=str, 
                        default='./SAM_mask/imagenet',
                        help='')
    args = parser.parse_args()
    return args

def processing_sam_concepts(sam_masks, image):
    """
    Process the regions divided by SAM to prevent intersection of sub-regions.
        sam_mask: Masks generated by Segment Anything Model
    """
    num = len(sam_masks)
    mask_sets_V = [mask['segmentation'].astype(np.uint8) for mask in sam_masks]

    for i in range(num-1):
        for j in range(i+1, num):
            intersection_region = (mask_sets_V[i] + mask_sets_V[j] == 2).astype(np.uint8)
            # no intersection region
            if intersection_region.sum() == 0:
                continue
            else:
                proportion_1 = intersection_region.sum() / mask_sets_V[i].sum()
                proportion_2 = intersection_region.sum() / mask_sets_V[j].sum()
                if proportion_1 > proportion_2:
                    mask_sets_V[j] -= intersection_region
                else:
                    mask_sets_V[i] -= intersection_region
    element_sets_V = []
    for mask in mask_sets_V:
        if mask.mean() > 0.0005:
            element_sets_V.append(image * mask[:,:,np.newaxis])
    element_sets_V.append(image - np.array(element_sets_V).sum(0).astype(np.uint8))

    return element_sets_V

def main(args):
    # Load model
    sam = sam_model_registry["vit_h"](checkpoint="ckpt/pytorch_model/sam_vit_h_4b8939.pth")
    sam.to("cuda")
    mask_generator = SamAutomaticMaskGenerator(sam, stability_score_thresh=0.8)
    
    # data preproccess
    with open(args.image_file, "r") as f:
        datas = f.read().split('\n')
    
    input_data = []
    label = []
    for data in datas[800:]:
        label.append(int(data.strip().split(" ")[-1]))
        input_data.append(
            data.split(" ")[0]
        )
    
    mkdir("SAM_mask")
    mkdir(args.save_dir)
    print("Begin Inference")
    for image_path, y_label in zip(input_data, label):
        try:
            if os.path.exists(os.path.join(args.save_dir, image_path.replace(".jpg", ".npy").replace(".JPEG", ".npy"))):
                continue
            
            image = cv2.imread(os.path.join(args.image_dir, image_path))

            masks = mask_generator.generate(cv2.cvtColor(image, cv2.COLOR_BGR2RGB))
            element_sets_V = processing_sam_concepts(masks, image)

            # mkdir(os.path.join(args.save_dir, str(y_label)))
            np.save(os.path.join(args.save_dir, image_path.replace(".jpg", "").replace(".JPEG", "")), np.array(element_sets_V))
        except:
            print("Image {} need larger CUDA.".format(image_path))
    return

if __name__ == "__main__":
    args = parse_args()
    main(args)