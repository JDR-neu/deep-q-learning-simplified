"""

Usage:
    run_dqn.py [options]

Options:
    --batch-size=<size>         Batch size [default: 32]
    --envid=<envid>             Environment id [default: SpaceInvadersNoFrameskip-v3]
    --timesteps=<steps>         Number of timesteps to run [default: 40000000]
    --learning-starts=<starts>  Timestep to start learning [default: 200000]
    --checkpoint-dir=<dir>      Directory containing checkpoints. [default: ./checkpoints]
    --restore=<restore>         File to restore model from (.ckpt for Tensorflow file, .npy for numpy)
"""

import dqn

from atari_wrappers import wrap_deepmind
from dqn_utils import get_wrapper_by_name
from dqn_utils import PiecewiseSchedule

import docopt
import gym
import numpy as np

from gym import wrappers
from numba import jit
from skimage.transform import pyramid_reduce

import os.path
import random

from typing import Dict
from typing import Tuple


def initialize_model(input_shape: Tuple, num_actions: int) -> Dict:
    """Initialize the model using gaussian Xavier initialization"""
    h, w, d = input_shape
    n = h * w * d
    return {'W0': np.random.normal(0, (1/n)**(1/2), size=(n, num_actions))}


def load_tf_model(
        restore: str,
        weights: str='q_func/action_value/fully_connected/weights') -> Dict:
    """Restore the model provided by a Tensorflow file."""
    import tensorflow as tf

    reader = tf.train.NewCheckpointReader(restore)
    return {'W0': reader.get_tensor(weights)}


@jit
def evaluate(X: np.ndarray, model: Dict) -> np.ndarray:
    """Evaluate the neural network."""
    W0 = model['W0']
    l0 = X.reshape((X.shape[0], W0.shape[0]))
    l1 = np.maximum(0, l0.dot(W0))
    return l1


def featurize(X: np.ndarray, target=(84, 84, 4)) -> np.ndarray:
    """Featurize the provided data.

    Simple image compression, for now.
    """
    return pyramid_reduce(X, scale=X.shape[0]/target[0])


def set_global_seeds(i):
    """Set global random seeds."""
    np.random.seed(i)
    random.seed(i)


def get_env(env_id, seed):
    """Get gym environment, per id and seed."""
    env = gym.make(env_id)

    set_global_seeds(seed)
    env.seed(seed)

    expt_dir = './tmp/hw3_vid_dir2/'
    env = wrappers.Monitor(env, os.path.join(expt_dir, "gym"), force=True)
    env = wrap_deepmind(env)

    return env


def simplified_learn(env,
                num_timesteps,
                batch_size=32,
                learning_starts=200000,
                checkpoint_dir='./checkpoints',
                restore=None):
    # This is just a rough estimate
    num_iterations = float(num_timesteps) / 4.0
    learning_starts = int(learning_starts) / 4.0

    lr_multiplier = 1.0
    lr_schedule = PiecewiseSchedule([
             (0,                   1e-4 * lr_multiplier),
             (num_iterations / 10, 1e-4 * lr_multiplier),
             (num_iterations / 2,  5e-5 * lr_multiplier),
        ],
        outside_value=5e-5 * lr_multiplier)

    def stopping_criterion(env, t):
        # notice that here t is the number of steps of the wrapped env,
        # which is different from the number of steps in the underlying env
        return get_wrapper_by_name(env, "Monitor").get_total_steps() >= num_timesteps

    exploration_schedule = PiecewiseSchedule(
        [
            (0, 1.0),
            (1e6, 0.1),
            (num_iterations / 2 if num_iterations > 1e6 else 1e9, 0.01),
        ], outside_value=0.01
    )

    if restore is not None:
        initializer = lambda *args, **kwargs: load_tf_model(restore)
    else:
        initializer = initialize_model

    model = dqn.learn(
        env,
        initialize_model=initializer,
        q_func=evaluate,
        lr_schedule=lr_schedule,
        exploration=exploration_schedule,
        stopping_criterion=stopping_criterion,
        replay_buffer_size=1000000,
        batch_size=batch_size,
        learning_starts=learning_starts,
        learning_freq=4,
        frame_history_len=4,
        target_update_freq=10000,
        grad_norm_clipping=10,
        checkpoint_dir=checkpoint_dir
    )
    env.close()
    return model


def main():
    arguments = docopt.docopt(__doc__)

    # Run training
    seed = 0  # Use a seed of zero (you may want to randomize the seed!)
    env = get_env(arguments['--envid'], seed)

    batch_size = int(arguments['--batch-size'])
    simplified_learn(
        env,
        num_timesteps=int(arguments['--timesteps']),
        batch_size=batch_size,
        learning_starts=arguments['--learning-starts'],
        checkpoint_dir=arguments['--checkpoint-dir'],
        restore=arguments['--restore'])


if __name__ == '__main__':
    main()