# Import Time
import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import torchvision
from torchvision import transforms
from torch.utils.data import DataLoader

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

# Gets the GPU if there is one, otherwise the cpu
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
print(device)

# Quick function that gets how many out of 'preds' match 'labels'
# To be used much later
def get_num_correct(preds, labels):
    return preds.argmax(dim=1).eq(labels).sum().item()

# Read in the train set and the test set
# In a kernel here on Kaggle, use the Workspace on the right-hand side to figure out the file path
train_set = pd.read_csv("./data/mnist_train.csv")
test_images = pd.read_csv("./data/mnist_test.csv")

# Split the train set so there is also a validation set
train_images, val_images, train_labels, val_labels = train_test_split(train_set.iloc[:, 1:], 
                                                                     train_set.iloc[:, 0], 
                                                                     test_size=0.2)

# Reset indices so the Dataset can find them with __getitem__ easily
train_images.reset_index(drop=True, inplace=True)
val_images.reset_index(drop=True, inplace=True)
train_labels.reset_index(drop=True, inplace=True)
val_labels.reset_index(drop=True, inplace=True)

# Transformations
IMG_SIZE = 28 # size of images in MNIST
# Also the images only have one color channel
# So 3D size = (1, 28, 28)

# Transformations for the train
train_trans = transforms.Compose(([
    transforms.ToPILImage(),
    transforms.RandomCrop(IMG_SIZE), 
    transforms.ToTensor(), # divides by 255
  #  transforms.Normalize((0.5,), (0.5,))
]))

# Transformations for the validation & test sets
val_trans = transforms.Compose(([
    transforms.ToPILImage(),
    transforms.ToTensor(), # divides by 255
   # transforms.Normalize((0.1307,), (0.3081,))
]))

class MNISTDataSet(torch.utils.data.Dataset):
    # images df, labels df, transforms
    # uses labels to determine if it needs to return X & y or just X in __getitem__
    def __init__(self, images, labels, transforms=None):
        self.X = images
        self.y = labels
        self.transforms = transforms
                    
    def __len__(self):
        return len(self.X)
    
    def __getitem__(self, i):
        data = self.X.iloc[i, :] # gets the row
        # reshape the row into the image size 
        # (numpy arrays have the color channels dim last)
        data = np.array(data).astype(np.uint8).reshape(28, 28, 1) 
        
        # perform transforms if there are any
        if self.transforms:
            data = self.transforms(data)
        
        # if !test_set return the label as well, otherwise don't
        if self.y is not None: # train/val
            return (data, self.y[i])
        else: # test
            return data

# Get datasets using the custom MNIST Dataset for the train, val, and test images
train_set = MNISTDataSet(train_images, train_labels, train_trans)
val_set = MNISTDataSet(val_images, val_labels, val_trans)
test_set = MNISTDataSet(test_images, None, val_trans)

# Nice habit to get into
num_classes = 10 # 0-9


class Network(nn.Module):
    def __init__(self):
        super(Network, self).__init__()
        # image starts as (1, 28, 28)
        # Formula to compute size of image after conv/pool
        # (size-filter+2*padding / stride) + 1
        #                      inputs         # of filters    filter size    
        self.conv1 = nn.Conv2d(in_channels=1, out_channels=32, kernel_size=5, stride=1, padding=2) # conv1
        self.conv1_bn = nn.BatchNorm2d(num_features=32)
        self.conv2 = nn.Conv2d(in_channels=32, out_channels=64, kernel_size=5, stride=1, padding=2) # conv2
        self.conv2_bn = nn.BatchNorm2d(num_features=64)
        self.conv3 = nn.Conv2d(in_channels=64, out_channels= 128, kernel_size=3, stride=1, padding=1) # conv3
        self.conv3_bn = nn.BatchNorm2d(num_features=128)
        
        self.fc1 = nn.Linear(in_features=128*6*6, out_features=1024) # linear 1
        self.fc1_bn = nn.BatchNorm1d(num_features=1024)
        self.fc2 = nn.Linear(in_features=1024, out_features=512) # linear 2
        self.fc2_bn = nn.BatchNorm1d(num_features=512)
        self.fc3 = nn.Linear(in_features=512, out_features=256) # linear 3
        self.fc3_bn = nn.BatchNorm1d(num_features=256)
        self.fc4 = nn.Linear(in_features=256, out_features=64) # linear 4
        self.fc4_bn = nn.BatchNorm1d(num_features=64)
        self.out = nn.Linear(in_features=64, out_features=10) # output
    
    def forward(self, t):
        t = F.relu(self.conv1_bn(self.conv1(t)))
        t = F.max_pool2d(t, kernel_size=2, stride=2) # (1, 14, 14)
        
        t = F.relu(self.conv2_bn(self.conv2(t)))
        t = F.max_pool2d(t, kernel_size=2, stride=2) # (1, 7, 7)
        
        t = F.relu(self.conv3_bn(self.conv3(t)))
        t = F.max_pool2d(t, kernel_size=2, stride=1) # (1, 6, 6)
        
        t = F.relu(self.fc1_bn(self.fc1(t.reshape(-1, 128*6*6))))
        t = F.relu(self.fc2_bn(self.fc2(t)))
        t = F.relu(self.fc3_bn(self.fc3(t)))
        t = F.relu(self.fc4_bn(self.fc4(t)))
        t = self.out(t)
        
        return t


lr = 0.001 # initial learning rate
batch_size = 100 # batch size
epochs = 10 # number of epochs to run

network = Network().to(device) # put the model on device (hopefully a GPU!)
train_dl = DataLoader(train_set, batch_size=batch_size, shuffle=True)
val_dl = DataLoader(val_set, batch_size=batch_size, shuffle=False)
optimizer = optim.Adam(network.parameters(), lr=lr)

for epoch in range(epochs):
    print("Epoch: ", epoch+1)
    epoch_loss = 0
    epoch_correct = 0
    network.train() # training mode
    
    # lessen the learning rate after 4 epochs (0,...,3)
    if epoch == 4:
        print(" decreasing lr")
        optimizer = optim.Adam(network.parameters(), lr=0.00001)
    
    if epoch == 10: # not currently used
        print(" decreasing lr again")
        optimizer = optim.Adam(network.parameters(), lr=0.0000000000001)
    
    for images, labels in train_dl:
        X, y = images.to(device), labels.to(device) # put X & y on device
        y_ = network(X) # get predictions
        
        optimizer.zero_grad() # zeros out the gradients
        loss = F.cross_entropy(y_, y) # computes the loss
        loss.backward() # computes the gradients
        optimizer.step() # updates weights
        
        epoch_loss += loss.item() * batch_size
        epoch_correct += get_num_correct(y_, y)
        
    # Evaluation with the validation set
    network.eval() # eval mode
    val_loss = 0
    val_correct = 0
    with torch.no_grad():
        for images, labels in val_dl:
            X, y = images.to(device), labels.to(device) # to device
            
            preds = network(X) # get predictions
            loss = F.cross_entropy(preds, y) # calculate the loss
            
            val_correct += get_num_correct(preds, y)
            val_loss = loss.item() * batch_size
    # Print the loss and accuracy for the validation set
    print(" Val Loss: ", val_loss)
    print(" Val Acc: ", (val_correct/len(val_images))*100)



