import random

# using lists instead of named vars to keep it short.
CONFIG_mkB = {
    'seed': None,
    'means': [25, 40, 20, 40], # mean times of all stages: next/prep/op/rec
    'unif': [None, (20,20), None, None], #uniform dist. params. if None then use 'means' with expovar.
    'total': [5,2,5], # useable + starting slack (unused/offline) capacity for each facility type.
    'staffed': [3, 1, 3], # useable totals of each identical facility: prep/op/rec
    'monitor_interval': 5 # snapshot interval for non-patient variables, such as queues
}
