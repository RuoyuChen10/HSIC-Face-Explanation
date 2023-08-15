import argparse

import os
import cv2
import numpy as np
import tensorflow as tf
from matplotlib import pyplot as plt
import tensorflow_addons as tfa
from keras.models import load_model

import xplique
# from xplique.plots import plot_attributions
from insight_face_models import *
from xplique.metrics import Deletion
# from xplique.metrics import Insertion
from tqdm import tqdm

from PIL import Image
import torchvision.transforms as transforms

def load_image(path, size=112):
    img = cv2.resize(cv2.imread(path)[...,::-1], (size, size))
    img = (img - 127.5) * 0.0078125
    return img.astype(np.float32)

def prepare_image(img, size=112):
    img = cv2.resize(img[...,::-1], (size, size))
    img = np.array([(img - 127.5) * 0.0078125])
    return img.astype(np.float32)

def parse_args():
    parser = argparse.ArgumentParser(description='Deletion Metric')
    # general
    parser.add_argument('--Datasets',
                        type=str,
                        default='datasets/celeb-a/test',
                        help='Datasets.')
    parser.add_argument('--eval-list',
                        type=str,
                        default='datasets/celeb-a/eval.txt',
                        help='Datasets.')
    parser.add_argument('--eval-number',
                        type=int,
                        default=28,
                        help='Datasets.')
    parser.add_argument('--save-region-rate',
                        type=float,
                        default=0.1,
                        help='Datasets.')
    parser.add_argument('--save-set-number',
                        type=int,
                        default=10, # 28x28 8, 0.2: 20; 0.3: 29; 0.4: 39
                        help='Datasets.')
    parser.add_argument('--explanation-method', 
                        type=str, 
                        default='./explanation_results/celeba/HsicAttributionMethod',
                        # default='./explanation_results/celeba/Rise',
                        help='Save path for saliency maps generated by interpretability methods.')
    parser.add_argument('--explanation-smdl', 
                        type=str, 
                        default='./submodular_results/celeba/grad-28x28-8/HsicAttributionMethod-97-1.0-1.0-1.0/npy',
                        # default='./submodular_results/celeba/random_patch-7x7-48/npy',
                        help='output directory to save results')
    parser.add_argument('--mode-data', 
                        type=str, 
                        default='Celeb-A',
                        # choices=['Celeb-A', "VGGFace2"],
                        help='')
    args = parser.parse_args()
    return args

def Partition_image(image, explanation_mask, partition_rate=0.3):
    b,g,r = cv2.split(image)
    explanation_mask_flatten = explanation_mask.flatten()
    index = np.argsort(-explanation_mask_flatten)

    partition_number = int(len(explanation_mask_flatten) * partition_rate)

    b_tmp = b.flatten()
    g_tmp = g.flatten()
    r_tmp = r.flatten()
    
    b_tmp[index[partition_number : ]] = 0
    g_tmp[index[partition_number : ]] = 0
    r_tmp[index[partition_number : ]] = 0

    b_tmp = b_tmp.reshape((image.shape[0], image.shape[1]))
    g_tmp = g_tmp.reshape((image.shape[0], image.shape[1]))
    r_tmp = r_tmp.reshape((image.shape[0], image.shape[1]))

    img_tmp = cv2.merge([b_tmp, g_tmp, r_tmp])

    return img_tmp

def main(args):
    if args.mode_data == "Celeb-A":
        keras_model_path = "ckpt/keras_model/keras-ArcFace-R100-Celeb-A.h5"
        model = load_model(keras_model_path)
        class_number = 10177

    elif args.mode_data == "VGGFace2":
        keras_model_path = "ckpt/keras_model/keras-ArcFace-R100-VGGFace2.h5"
        model = load_model(keras_model_path)
        class_number = 8631

    # data preproccess
    with open(args.eval_list, "r") as f:
        datas = f.read().split('\n')

    org_acc = 0
    smdl_acc = 0
    for data in tqdm(datas[ : args.eval_number]):
        label = int(data.strip().split(" ")[-1])
        input_image = cv2.imread(os.path.join(args.Datasets, data.split(" ")[0]))
        explanation = np.load(
                os.path.join(args.explanation_method, data.split(" ")[0].replace(".jpg", ".npy")))
        smdl_mask = np.load(
                os.path.join(args.explanation_smdl, data.split(" ")[0].replace(".jpg", ".npy")))
        
        exp_image = prepare_image(
            input_image - Partition_image(input_image, explanation, args.save_region_rate))
        smdl_image = prepare_image(
            input_image - smdl_mask[ : args.save_set_number].sum(0))

        predict = model(exp_image)
        predict_idx = predict.numpy().argmax()
        if predict_idx == label:
            org_acc += 1

        predict = model(smdl_image)
        predict_idx = predict.numpy().argmax()
        if predict_idx == label:
            smdl_acc += 1

    print("Original Attribution Method at {} maintain rate ACC: {}".format(args.save_region_rate, org_acc / args.eval_number))
    print("Our Method at {} maintain rate ACC: {}".format(args.save_region_rate, smdl_acc / args.eval_number))

    return

if __name__ == "__main__":
    args = parse_args()
    main(args)