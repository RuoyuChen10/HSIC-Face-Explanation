# -*- coding: utf-8 -*-  

"""
Created on 2024/6/3

@author: Ruoyu Chen
"""

import os
os.environ["CUDA_VISIBLE_DEVICES"] = "0"

import numpy as np
import cv2
import math
from PIL import Image
from matplotlib import pyplot as plt
from tqdm import tqdm

from open_clip import create_model_from_pretrained, get_tokenizer

from xplique.wrappers import TorchWrapper
from xplique.plots import plot_attributions
from xplique.attributions import (Saliency, GradientInput, IntegratedGradients, SmoothGrad, VarGrad,
                                  SquareGrad, GradCAM, Occlusion, Rise, GuidedBackprop,
                                  GradCAMPP, Lime, KernelShap, SobolAttributionMethod, HsicAttributionMethod)

import torch
from torchvision import transforms

import tensorflow as tf
from utils import *

tf.config.run_functions_eagerly(True)

gpus = tf.config.experimental.list_physical_devices(device_type='GPU')
tf.config.experimental.set_virtual_device_configuration(
    gpus[0],
    [tf.config.experimental.VirtualDeviceConfiguration(memory_limit=4096)]
)

SAVE_PATH = "explanation_results/"
mkdir(SAVE_PATH)

mode = "Quilt"
net_mode  = "Quilt" # "resnet", vgg

if mode == "Quilt":
    if net_mode == "Quilt":
        img_size = 224
        dataset_index = "datasets/medical_lung/LC25000_lung_quilt_1k_false.txt"
        SAVE_PATH = os.path.join(SAVE_PATH, "lung-quilt-false")
    # elif net_mode == "languagebind":
        
    dataset_path = "datasets/medical_lung/lung_dataset"
    class_number = 3
    batch = 100
    mkdir(SAVE_PATH)

class QuiltModel_Super(torch.nn.Module):
    def __init__(self, 
                 download_root=".checkpoints/QuiltNet-B-32",
                 device = "cuda"):
        super().__init__()
        self.model, _ = create_model_from_pretrained('hf-hub:wisdomik/QuiltNet-B-32', cache_dir=download_root)
        self.device = device
            
    def forward(self, vision_inputs):
        
        with torch.no_grad():
            image_features = self.model.encode_image(vision_inputs)
            # image_features /= image_features.norm(dim=-1, keepdim=True)
        
        scores = (image_features @ self.semantic_feature.T).softmax(dim=-1)
        return scores.float()

data_transform = transforms.Compose(
        [
            transforms.Resize(
                (224,224), interpolation=transforms.InterpolationMode.BICUBIC
            ),
            # transforms.CenterCrop(224),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=(0.48145466, 0.4578275, 0.40821073),
                std=(0.26862954, 0.26130258, 0.27577711),
            ),
        ]
    )

def load_and_transform_vision_data(image_paths, device, channel_first=False):
    if image_paths is None:
        return None

    image_outputs = []
    
    for image_path in image_paths:
        with open(image_path, "rb") as fopen:
            image = Image.open(fopen).convert("RGB")

        image = data_transform(image).to(device)
        image_outputs.append(image)
    image_outputs = torch.stack(image_outputs, dim=0)
    if channel_first:
        pass
    else:
        image_outputs = image_outputs.permute(0,2,3,1)
    return image_outputs.cpu().numpy()   

def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    # Load model
    vis_model = QuiltModel_Super()
    vis_model.eval()
    vis_model.to(device)
    print("load Quilt-1M model")
    
    tokenizer = get_tokenizer('hf-hub:wisdomik/QuiltNet-B-32')
    texts = tokenizer([lc_lung_template + l for l in lc_lung_classes], context_length=77).to(device)

    with torch.no_grad():
        semantic_feature = vis_model.model.encode_text(texts) * 10
    
    vis_model.semantic_feature = semantic_feature
    
    wrapped_model = TorchWrapper(vis_model.eval(), device)
    
    batch_size = 64
    
    # define explainers
    explainers = [
        # Saliency(model),
        # GradientInput(model),
        # GuidedBackprop(model),
        # IntegratedGradients(model, steps=80, batch_size=batch_size),
        # SmoothGrad(model, nb_samples=80, batch_size=batch_size),
        # SquareGrad(model, nb_samples=80, batch_size=batch_size),
        # VarGrad(model, nb_samples=80, batch_size=batch_size),
        # GradCAM(model),
        # GradCAMPP(model),
        # Occlusion(model, patch_size=10, patch_stride=5, batch_size=batch_size),
        # Rise(model, nb_samples=500, batch_size=batch_size),
        # SobolAttributionMethod(model, batch_size=batch_size),
        HsicAttributionMethod(wrapped_model, batch_size=batch_size),
        Rise(wrapped_model, nb_samples=500, batch_size=batch_size),
        # Lime(model, nb_samples = 1000),
        # KernelShap(model, nb_samples = 1000, batch_size=32)
    ]
    
    # data preproccess
    with open(dataset_index, "r") as f:
        datas = f.read().split('\n')
    
    input_data = []
    label = []
    for data in datas:
        label.append(int(data.strip().split(" ")[-1]))
        input_data.append(
            os.path.join(dataset_path, data.split(" ")[0])
        )
    
    total_steps = math.ceil(len(input_data) / batch)
    
    for explainer in explainers:
        # explanation methods    
        explainer_method_name = explainer.__class__.__name__
        exp_save_path = os.path.join(SAVE_PATH, explainer_method_name)
        mkdir(exp_save_path)
        
        for step in tqdm(range(total_steps), desc=explainer_method_name):
            image_names = input_data[step * batch : step * batch + batch]
            X_raw = load_and_transform_vision_data(image_names, device)

            Y_true = np.array(label[step * batch : step * batch + batch])
            labels_ohe = np.eye(class_number)[Y_true]
            
            explanations = explainer(X_raw, labels_ohe)
            if type(explanations) != np.ndarray:
                explanations = explanations.numpy()
            
            for explanation, image_name in zip(explanations, image_names):
                mkdir(exp_save_path)
                np.save(os.path.join(exp_save_path, image_name.split("/")[-1].replace(".JPEG", "")), explanation)
    
    return

main()