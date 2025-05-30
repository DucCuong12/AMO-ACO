from collections import namedtuple
import numpy as np
import torch
from torch_geometric.data import Data
import os 

# device =  torch.device("cuda:0" if True == True else "cpu")
device = None 

size = 1
time_factor = 100
service_duration = 10
tw_expansion = 3
service_window = 1000
loc = 15
scale = 10
max_ = 42

CVRPTW_SET = namedtuple("CVRPTW_SET",
                        ["depot_loc",    # Depot location
                         "node_loc",     # Node locations
                         "demand",       # demand per node
                         "capacity",     # vehicle capacity (homogeneous)
                         "depot_tw",     # depot time window (full horizon)
                         "node_tw",      # node time windows
                         "durations",    # service duration per node
                        ])   

TW_CAPACITIES = {
        20: 70.,
        50: 100.,
        100: 200.,
        150: 500.,
        200: 700. 
    }

def generate_cvrptw_data(graph_size = 100):
    # sample locations
    rnds = np.random
    dloc = rnds.uniform(size=(size, 2))  # depot location
    nloc = rnds.uniform(size=(size, graph_size, 2))  # node locations

    # TW start needs to be feasibly reachable directly from depot
    min_t = np.ceil(np.linalg.norm(dloc[:, None, :]*time_factor - nloc*time_factor, axis=-1)) + 1
    # TW end needs to be early enough to perform service and return to depot until end of service window
    max_t = np.ceil(np.linalg.norm(dloc[:, None, :]*time_factor - nloc*time_factor, axis=-1) + service_duration) + 1

    # horizon allows for the feasibility of reaching nodes / returning from nodes within the global tw (service window)
    horizon = list(zip(min_t, service_window - max_t))
    epsilon = np.maximum(np.abs(rnds.standard_normal([size, graph_size])), 1 / time_factor)

    # sample earliest start times a
    a = [rnds.randint(*h) for h in horizon]

    tw = [np.transpose(np.vstack((rt,  # a
                                  np.minimum(rt + tw_expansion * time_factor * sd, h[-1]).astype(int)  # b
                                  ))).tolist()
          for rt, sd, h in zip(a, epsilon, horizon)]

    a = [CVRPTW_SET(*data) for data in zip(
        torch.tensor(dloc.tolist(), device = device) * time_factor,
        torch.tensor(nloc.tolist(), device = device) * time_factor,
        torch.tensor(np.minimum(np.maximum(np.abs(rnds.normal(loc=loc, scale=scale, size=[size, graph_size])).astype(int), 1), max_).tolist(), device = device),
        torch.tensor(np.full(size, TW_CAPACITIES[graph_size]).tolist(), device = device),
        torch.tensor([[0, service_window]] * size, dtype = torch.float32, device = device),
        torch.tensor(tw, dtype = torch.float32, device = device),
        torch.tensor(np.full([size, graph_size], service_duration).tolist(), device = device)
    )]
    return a[0]


def gen_valid_data(file_path, graph_size = 100): 
    # sample locations
    rnds = np.random
    dloc = rnds.uniform(size=(size, 2))  # depot location
    nloc = rnds.uniform(size=(size, graph_size, 2))  # node locations

    # TW start needs to be feasibly reachable directly from depot
    min_t = np.ceil(np.linalg.norm(dloc[:, None, :]*time_factor - nloc*time_factor, axis=-1)) + 1
    # TW end needs to be early enough to perform service and return to depot until end of service window
    max_t = np.ceil(np.linalg.norm(dloc[:, None, :]*time_factor - nloc*time_factor, axis=-1) + service_duration) + 1

    # horizon allows for the feasibility of reaching nodes / returning from nodes within the global tw (service window)
    horizon = list(zip(min_t, service_window - max_t))
    epsilon = np.maximum(np.abs(rnds.standard_normal([size, graph_size])), 1 / time_factor)

    # sample earliest start times a
    a = [rnds.randint(*h) for h in horizon]

    tw = [np.transpose(np.vstack((rt,  # a
                                  np.minimum(rt + tw_expansion * time_factor * sd, h[-1]).astype(int)  # b
                                  ))).tolist()
          for rt, sd, h in zip(a, epsilon, horizon)]

    a = [CVRPTW_SET(*data) for data in zip(
        torch.tensor(dloc.tolist(), device = device) * time_factor,
        torch.tensor(nloc.tolist(), device = device) * time_factor,
        torch.tensor(np.minimum(np.maximum(np.abs(rnds.normal(loc=loc, scale=scale, size=[size, graph_size])).astype(int), 1), max_).tolist(), device = device),
        torch.tensor(np.full(size, TW_CAPACITIES[graph_size]).tolist(), device = device),
        torch.tensor([[0, service_window]] * size, dtype = torch.float32, device = device),
        torch.tensor(tw, dtype = torch.float32, device = device),
        torch.tensor(np.full([size, graph_size], service_duration).tolist(), device = device)
    )]
    return a[0]








def gen_pyg_data(demands, time_window, durations, distances, device, scale = 1000.0):
    n = demands.size(0)
    nodes = torch.arange(n, device=device)
    u = nodes.repeat(n)
    v = torch.repeat_interleave(nodes, n)
    edge_index = torch.stack((u, v))
    edge_attr = distances.reshape(((n)**2, 1))
    x = demands
    x = torch.where(x == 0, 1e-7, x)
    edge_attr = torch.where(edge_attr == 0, 1e-7, edge_attr)
    pyg_data = Data(x=x.unsqueeze(1), edge_attr=edge_attr, edge_index=edge_index, time_window = time_window, durations = durations)
    return pyg_data

def gen_pyg_data_normalize(demands, time_window, durations, distances, device, scale = 1000.0):
    n = demands.size(0)
    nodes = torch.arange(n, device=device)
    u = nodes.repeat(n)
    v = torch.repeat_interleave(nodes, n)
    edge_index = torch.stack((u, v))
    edge_attr = distances.reshape(((n)**2, 1))
    x = demands
    x = torch.where(x == 0, 1e-7, x)
    edge_attr = torch.where(edge_attr == 0, 1e-7, edge_attr)
    pyg_data = Data(x=x.unsqueeze(1) / capacity, edge_attr=edge_attr/scale, edge_index=edge_index, time_window = time_window/scale, durations = durations/scale)
    return pyg_data

def gen_distance_matrix(tsp_coordinates, device):
    n_nodes = len(tsp_coordinates)
    distances = torch.norm(tsp_coordinates[:, None] - tsp_coordinates, dim=2, p=2)
    return distances



CVRPTW = generate_cvrptw_data(200)
capacity = (int)(CVRPTW.capacity)

def write_to_gen8_file(data, filename):
    with open(filename, 'w') as file:
        file.write("Gen8\n\n")
        file.write("VEHICLE\n")
        file.write("NUMBER     CAPACITY\n")
        file.write(f"30     {capacity}\n\n")
        file.write("CUSTOMER\n")
        file.write("CUST NO.     XCOORD.     YCOORD.     DEMAND     READY TIME     DUE DATE     SERVICE TIME\n\n")
        for row in data:
            file.write("    ".join(map(str, row)) + "\n")


data = []
data.append([0])
for i in CVRPTW.depot_loc:
    data[0].append((int)(i.item()))
data[0].append(0)
for i in CVRPTW.depot_tw:
    data[0].append((int)(i.item()))
data[0].append(0)

for i in range(len(CVRPTW.node_loc)):
    data.append([i+1])
    for j in CVRPTW.node_loc[i]:
        data[i+1].append((int)(j.item()))
    data[i+1].append((int)(CVRPTW.demand[i].item()))
    for j in CVRPTW.node_tw[i]:
        data[i+1].append((int)(j.item()))
    data[i+1].append((int)(CVRPTW.durations[i].item()))

write_to_gen8_file(data, 'Mock_data/200/3.txt')