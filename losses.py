# reference code: https://github.com/kaidic/LDAM-DRW/blob/master/cifar_train.py
import math
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from opts import parser

args = parser.parse_args()
if args.dataset == 'cifar100':
    num_classes = 100
elif args.dataset == 'cifar10':
    num_classes = 10
else:  # iNat18
    num_classes = 8142
    

def focal_loss(input_values, gamma):
    """Computes the focal loss"""
    p = torch.exp(-input_values)
    # loss = (1 - p) ** gamma * input_values
    loss = (1 - p) ** gamma * input_values * 10
    return loss.mean()


class FocalLoss(nn.Module):
    def __init__(self, weight=None, gamma=0.):
        super(FocalLoss, self).__init__()
        assert gamma >= 0
        self.gamma = gamma
        self.weight = weight

    def forward(self, input, target):
        return focal_loss(F.cross_entropy(input, target, reduction='none', weight=self.weight), self.gamma)


class LDAMLoss(nn.Module):
    def __init__(self, cls_num_list, max_m=0.5, weight=None, s=30):
        super(LDAMLoss, self).__init__()
        m_list = 1.0 / np.sqrt(np.sqrt(cls_num_list))
        m_list = m_list * (max_m / np.max(m_list))
        m_list = torch.cuda.FloatTensor(m_list)
        self.m_list = m_list
        assert s > 0
        self.s = s
        self.weight = weight

    def forward(self, x, target):
        index = torch.zeros_like(x, dtype=torch.uint8)
        index.scatter_(1, target.data.view(-1, 1), 1)

        index_float = index.type(torch.cuda.FloatTensor)
        batch_m = torch.matmul(self.m_list[None, :], index_float.transpose(0, 1))
        batch_m = batch_m.view((-1, 1))
        x_m = x - batch_m

        output = torch.where(index, x_m, x)
        return F.cross_entropy(self.s * output, target, weight=self.weight)


class BalancedSoftmaxLoss(nn.Module):
    def __init__(self, cls_num_list):
        super().__init__()
        cls_prior = cls_num_list / sum(cls_num_list)
        self.log_prior = torch.log(cls_prior).unsqueeze(0)
        # self.min_prob = 1e-9
        # print(f'Use BalancedSoftmaxLoss, class_prior: {cls_prior}')

    def forward(self, logits, labels):
        adjusted_logits = logits + self.log_prior
        label_loss = F.cross_entropy(adjusted_logits, labels)

        return label_loss

class EffBalancedSoftmaxLoss(nn.Module):
    def __init__(self, cls_num_list):
        super().__init__()
        beta = 0.9999
        cls_num_list = 1.0 - torch.pow(beta, cls_num_list)
        cls_prior = cls_num_list / sum(cls_num_list)
        #cls_prior = torch.FloatTensor(cls_prior).cuda(args.gpu)
        self.log_prior = torch.log(cls_prior).unsqueeze(0)
        # self.min_prob = 1e-9
        # print(f'Use BalancedSoftmaxLoss, class_prior: {cls_prior}')

    def forward(self, logits, labels):
        adjusted_logits = logits + self.log_prior
        label_loss = F.cross_entropy(adjusted_logits, labels)

        return label_loss
        
class EffBalancedSoftmax(nn.Module):
    def __init__(self, cls_num_list):
        super().__init__()
        beta = 0.9999
        cls_num_list = 1.0 - torch.pow(beta, cls_num_list)
        cls_prior = cls_num_list / sum(cls_num_list)
        #cls_prior = torch.FloatTensor(cls_prior).cuda(args.gpu)
        self.log_prior = torch.log(cls_prior).unsqueeze(0)
        # self.min_prob = 1e-9
        # print(f'Use BalancedSoftmaxLoss, class_prior: {cls_prior}')

    def forward(self, logits):
        adjusted_logits = logits + self.log_prior
        #label_loss = F.cross_entropy(adjusted_logits, labels)

        return adjusted_logits
    

def ib_loss(input_values, ib):
    """Computes the focal loss"""
    loss = input_values * ib
    return loss.mean()

class IBLoss(nn.Module):
    def __init__(self, weight=None, alpha=10000.):
        super(IBLoss, self).__init__()
        assert alpha > 0
        self.alpha = alpha
        self.epsilon = 0.001
        self.weight = weight

    def forward(self, input, target, features):
        grads = torch.sum(torch.abs(F.softmax(input, dim=1) - F.one_hot(target, num_classes)),1) # N * 1
        ib = grads*features.reshape(-1)
        ib = self.alpha / (ib + self.epsilon)
        return ib_loss(F.cross_entropy(input, target, reduction='none', weight=self.weight), ib)

def ib_focal_loss(input_values, ib, gamma):
    """Computes the ib focal loss"""
    p = torch.exp(-input_values)
    loss = (1 - p) ** gamma * input_values * ib
    return loss.mean()

class IB_FocalLoss(nn.Module):
    def __init__(self, weight=None, alpha=10000., gamma=0.):
        super(IB_FocalLoss, self).__init__()
        assert alpha > 0
        self.alpha = alpha
        self.epsilon = 0.001
        self.weight = weight
        self.gamma = gamma

    def forward(self, input, target, features):
        grads = torch.sum(torch.abs(F.softmax(input, dim=1) - F.one_hot(target, num_classes)),1) # N * 1
        ib = grads*(features.reshape(-1))
        ib = self.alpha / (ib + self.epsilon)
        return ib_focal_loss(F.cross_entropy(input, target, reduction='none', weight=self.weight), ib, self.gamma)

