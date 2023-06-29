# will try to implement some easy variant of td learning
# not sure if I will use my custom gym environment, as it is not really necessary
import wandb
import pandas as pd
import numpy as np
import os
import pickle
import torch
from torch import nn
from torch.nn import functional as F
import torch.optim as optim
from sklearn import preprocessing
from torch.utils.data import DataLoader, Dataset

# plotting
import matplotlib.pyplot as plt

from RL.RL_algos_custom import eval_funcs

from sklearn.preprocessing import MinMaxScaler, StandardScaler
# X_std = (X - X.min(axis=0)) / (X.max(axis=0) - X.min(axis=0))
# X_scaled = X_std * (max - min) + min



"""
update the window on a rolling window

"""


##### CHECK IF THE DATES ACTUALLY CORRESPOND TO EACH OTHER!!!!!!!!!!!!!!!!!!!!!!!!!!
# they do according to a QUICK MANUAL CHECK..

# IMPORT SHRK DATASETS
shrk_data_path = r'C:\Users\Damja\OneDrive\Damjan\FS23\master-thesis\code\shrk_datasets'
pf_size = 100
with open(rf"{shrk_data_path}\fixed_shrkges_p{pf_size}.pickle", 'rb') as f:
    fixed_shrk_data = pickle.load(f)
with open(rf"{shrk_data_path}\factor-1.0_p{pf_size}.pickle", 'rb') as f:
    optimal_shrk_data = pickle.load(f)

# IMPORT FACTORS DATA AND PREPARE FOR FURTHER USE
factor_path = r"C:\Users\Damja\OneDrive\Damjan\FS23\master-thesis\code\factor_data"
factors = pd.read_csv(factor_path + "/all_factors.csv")
factors = factors.pivot(index="date", columns="name", values="ret")

# as our shrk data starts from 1980-01-15 our factors data should too
start_date = '1980-01-15'
start_idx = np.where(factors.index == start_date)[0][0]
factors = factors.iloc[start_idx:start_idx+fixed_shrk_data.shape[0], :]


# Even for a simple TD-Learning method, we need an estimate of the Q(s,a) or V(s) function
# As we have a continuous state space, we should use a NN to parametrize this

class ActorCritic(nn.Module):
    def __init__(self, num_features, num_actions, hidden_size):
        super().__init__()
        ### NOTE: can share some layers of the actor and critic network as they have the same structure
        self.fc1 = nn.Linear(num_features, hidden_size)
        self.fc2 = nn.Linear(hidden_size, int(hidden_size/2))

        self.state_action_head = nn.Linear(int(hidden_size/2), num_actions)  # probabilistic mapping from states to actions
        #self.critic_head = nn.Linear(int(hidden_size/2), 1)  # estimated state value, I don't use this for now

        self.dropout = nn.Dropout(p=0.25)

    def forward(self, x):
        x = F.relu(self.fc1(x))
        x = self.dropout(x)
        x = F.relu(self.fc2(x))
        x = self.dropout(x)
        # get action distribution
        # action_probs = F.softmax(self.state_action_head(x), dim=1)
        # I DO NOT NEED PROBABILITEIS NOW
        state_action_value = self.state_action_head(x)
        # how 'good' is the current state?
        #state_value = self.critic_head(x)
        return state_action_value

# Train Loop
# first idea: for every data point, compare my state value estimates to the actual rewards



# TRAIN LOOP
def train_manual():

    train_indices = (0, int(factors.shape[0] * 0.7))
    val_indices = (int(factors.shape[0] * 0.7), factors.shape[0])


    for epoch in range(1, num_epochs+1):
        epoch_loss=[]
        validation_loss = []
        val_preds = []
        actual_argmin_validationset = []
        train_pf_std = []
        train_preds = []

        for i in range(train_indices[1]):
            inp = torch.Tensor(np.append(factors.iloc[i, :].values, optimal_shrk_data.iloc[i, 1])) * 100
            out = net(inp.view(1, -1))
            # hacking solution --> need to solve the problem that cols/rows of my data are of dtype=object !
            labels = torch.Tensor(np.array(fixed_shrk_data.iloc[i, 2:].values, dtype=float)).view(1, -1)
            train_preds.append(torch.argmin(out).item())

            # CALC LOSS AND BACKPROPAGATE
            optimizer.zero_grad()
            loss = criterion(out, labels)
            loss.backward()
            optimizer.step()
            epoch_loss.append(loss.item())

        # end of epoch statistics
        print(f"Loss of Epoch {epoch} (mean and sd): {np.mean(epoch_loss)}, {np.std(epoch_loss)}")
        if epoch % 10 == 0:
             print("break :-)")

        # validate at end of each epoch
        net.eval()
        stored_outputs = []
        stored_labels = []
        epoch_val_loss = []
        # NO TORCH.NO_GRAD() NOW, AS I NEED THE GRADIENTS...
        for i in range(val_indices[0], val_indices[1]):  # starting from point datapoint 21, will update network
            inp = torch.Tensor(np.append(factors.iloc[i, :].values, optimal_shrk_data.iloc[i, 1])) * 100
            out = net(inp.view(1, -1))
            labels = torch.Tensor(np.array(fixed_shrk_data.iloc[i, 2:].values, dtype=float)).view(1, -1)

            val_preds.append(torch.argmin(out).item())  # get action
            loss = criterion(out, labels)
            epoch_val_loss.append(loss.item())

            # store labels and output to update
            stored_labels.append(labels)
            stored_outputs.append(out)
            if i >= (val_indices[0] + 21): # we are enough in the future so we can update the network with data from val set (incrementally)
                net.train()
                optimizer.zero_grad()
                loss = criterion(stored_labels[i-21-val_indices[0]], stored_outputs[i-21-val_indices[0]])
                loss.backward()
                optimizer.step()
                net.eval()


        # END OF VALIDATION: CALCULATE LOSS METRICS AND PRINT THEM

        # print mean and sd of val loss
        print(f"Validation Loss of Epoch {epoch} (mean and sd): {np.mean(epoch_val_loss)}, {np.std(epoch_val_loss)}")
        # set model back into train mode

        pfstd1, pfstd2, pfstd1_sd, pfstd2_sd = eval_funcs.evaluate_preds(
                val_preds,
                optimal_shrk_data.iloc[val_indices[0]:val_indices[1], :],
                fixed_shrk_data.iloc[val_indices[0]:val_indices[1], :]
        )

        print(f"Validation pf std with shrkges chosen by network: {pfstd1} \n"
                  f"Validation pf std with shrkges chosen by cov1para: {pfstd2}")
        print(f"Validation sd of pf std's [network]: ", pfstd1_sd)
        print(f"Validation sd of pf std's [cov1para]: ", pfstd2_sd)
        print(f"Validation PF std epoch {epoch} [QIS] (mean): {0.10245195394691942}")
        print(f"Validation minimum attainable pf sd: ", 0.09259940834962073)


        y2 = optimal_shrk_data['shrk_factor'].iloc[val_indices[0]:val_indices[1]].values.tolist()
        if epoch == 5:
            print("done")
        mapped_val_preds = list(map(eval_funcs.f2_map, val_preds))
        # eval_funcs.myplot(y2, mapped_val_preds)
        net.train()



##### IMPLEMENTATION WITH DATALOADER


class MyDataset(Dataset):

    def __init__(self, factors, fixed_shrk_data, optimal_shrk_data, normalize=False):
        if normalize == True:  # for now only scale factors
            self.factors_scaler = MinMaxScaler()
            self.factors = pd.DataFrame(self.factors_scaler.fit_transform(factors))
        else:
            self.factors = factors
        self.fixed_shrk_data = fixed_shrk_data
        self.optimal_shrk_data = optimal_shrk_data
        print("loaded")


    def __len__(self):
        return self.factors.shape[0]

    def __getitem__(self, idx):
        # inputs multiplied by 100 works better
        inp = torch.Tensor(np.append(self.factors.iloc[idx, :].values, self.optimal_shrk_data.iloc[idx, 1])) * 100
        labels = np.array(self.fixed_shrk_data.iloc[idx, 2:].values, dtype=float)
        labels = StandardScaler().fit_transform(labels.reshape(-1, 1))
        labels = torch.Tensor(labels).squeeze()
        #labels = torch.Tensor(np.array(self.fixed_shrk_data.iloc[idx, 2:].values, dtype=float))
        # for labels: .view(1, -1) not needed when working with Dataset and DataLoader
        return inp, labels

def train_with_dataloader(normalize=False):

    # split dataset into train and test
    batch_size = 16
    total_num_batches = factors.shape[0] // batch_size
    len_train = int(total_num_batches * 0.7) * batch_size
    train_dataset = MyDataset(
        factors.iloc[:len_train, :],
        fixed_shrk_data.iloc[:len_train, :],
        optimal_shrk_data.iloc[:len_train, :],
        normalize=normalize
    )

    val_dataset = MyDataset(
        factors.iloc[len_train:, :],
        fixed_shrk_data.iloc[len_train:, :],
        optimal_shrk_data.iloc[len_train:, :],
        normalize=False,
    )
    if normalize == True:
        val_dataset.factors = pd.DataFrame(train_dataset.factors_scaler.transform(val_dataset.factors))

    train_dataloader = DataLoader(train_dataset)
    val_dataloader = DataLoader(val_dataset)


    validation_loss = []

    for epoch in range(1, num_epochs+1):
        train_preds = []
        val_preds = []
        actual_train_labels = []
        epoch_loss = []
        for i, data in enumerate(train_dataloader):
            X, labels = data  # labels are actually the annualized pf standard deviations [= "reward"]
            actual_train_labels.append(torch.argmin(labels).item())
            out = net(X.view(1, -1))
            train_preds.append(torch.argmin(out).item())
            opt_shrk = torch.tensor(optimal_shrk_data['shrk_factor'].iloc[i])
            out_shrk = torch.argmin(out) / 100
            # CALC LOSS AND BACKPROPAGATE
            optimizer.zero_grad()
            loss = criterion(out, labels)  # MSE between outputs of NN and pf std --> pf std can be interpreted
            # as value of taking action a in state s, hence want my network to learn this
            # loss += criterion(out_shrk, opt_shrk)
            loss.backward()
            optimizer.step()
            epoch_loss.append(loss.item())


        # end of epoch statistics
        print(f"Loss of Epoch {epoch} (mean and sd): {np.mean(epoch_loss)}, {np.std(epoch_loss)}")
        if epoch % 10 == 0:
            print("break :-)")
            # calc validation loss

        # log at end of epoch

        # validate at end of epoch
        # set model into evaluation mode and deactivate gradient collection
        net.eval()
        epoch_val_loss = []
        actual_argmin_validationset = []
        with torch.no_grad():
            for i, data in enumerate(val_dataloader):
                X, labels = data
                out = net(X.view(1, -1))
                val_preds.append(torch.argmin(out).item())
                loss = criterion(out, labels)
                epoch_val_loss.append(loss.item())

                actual_argmin_validationset.append(torch.argmin(labels).item())

            # print mean and sd of val loss
            print(f"Validation Loss of Epoch {epoch} (mean and sd): {np.mean(epoch_val_loss)}, {np.std(epoch_val_loss)}")
            # set model back into train mode

            # log the val loss

            # return mean pf std of opt shrk estimator and shrk estimators chosen by my network
            pfstd1, pfstd2, pfstd1_sd, pfstd2_sd = eval_funcs.evaluate_preds(val_preds,
                                                       val_dataset.optimal_shrk_data,
                                                       val_dataset.fixed_shrk_data)

            print(f"Validation pf std with shrkges chosen by network: {pfstd1} \n"
                  f"Validation pf std with shrkges chosen by cov1para: {pfstd2}")
            print(f"Validation sd of pf std's [network]: ", pfstd1_sd)
            print(f"Validation sd of pf std's [cov1para]: ", pfstd2_sd)
            print(f"Validation PF std epoch {epoch} [QIS] (mean): {0.10245195394691942}")
            print(f"Validation minimum attainable pf sd: ", 0.09259940834962073)

            mapped_shrkges = list(map(eval_funcs.f2_map, val_preds))


            #eval_funcs.simple_plot(val_preds, actual_argmin_validationset)
            #eval_funcs.simple_plot(val_preds, optimal_shrk_data["shrk_factor"], map1=True, map2=True)
            act_argmin_shrgks = list(map(eval_funcs.f2_map, actual_argmin_validationset))
            y2 = val_dataset.optimal_shrk_data["shrk_factor"].values.tolist()

            # eval_funcs.myplot(act_argmin_shrgks, mapped_shrkges, y2)
            # eval_funcs.myplot(mapped_shrkges, y2)

            '''
            eval_funcs.myplot(val_dataset.factors.iloc[:, 0].tolist(), val_dataset.factors.iloc[:, 1].tolist(), 
                              val_dataset.factors.iloc[:, 2].tolist(), val_dataset.factors.iloc[:, 3].tolist(), 
                              val_dataset.factors.iloc[:, 4].tolist(), val_dataset.factors.iloc[:, 4].tolist(), 
                              val_dataset.factors.iloc[:, 5].tolist(), val_dataset.factors.iloc[:, 6].tolist(), 
                              val_dataset.factors.iloc[:, 7].tolist(), y2)
            '''
            val_indices = (int(factors.shape[0] * 0.7), factors.shape[0])
            val_ds = fixed_shrk_data.iloc[val_indices[0]:val_indices[1], 2:]

            if epoch == 5:
                 print("F")


        net.train()


# PARAMETERS:
num_epochs = 20
lr = 1e-4
num_features = factors.shape[1] + 1  # all 13 factors + opt shrk
num_actions = fixed_shrk_data.shape[1] - 2  # since 1 col is dates, 1 col is hist vola
hidden_layer_size = 128
net = ActorCritic(num_features, num_actions, hidden_layer_size)
optimizer = optim.Adam(net.parameters(), lr=lr, weight_decay=1e-5)
criterion = nn.MSELoss()



# train_with_dataloader(normalize=False)

train_manual()

print("done")

