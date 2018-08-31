import os
import threading
import time
from tensorplex import Tensorplex

PORT = 8008
TB_FOLDER = '~/Temp/tensorplex/'

os.system('rm -rf "{}"'.format(TB_FOLDER))
os.system('mkdir -p "{}"'.format(TB_FOLDER))


tplex = Tensorplex(
    TB_FOLDER,
    max_processes=4,
)

def get_ablation_bin_name(tag):
    if tag in ['PPO', 'DDPG', 'DQN']:
        return 'RL'
    else:
        return 'Evolution'

(tplex
    .register_normal_group('learner')
    .register_indexed_group('agent', 8)
    .register_indexed_group('eval', 4)
    .register_combined_group('ablation', get_ablation_bin_name)
)

tplex.start_server(port=PORT)
