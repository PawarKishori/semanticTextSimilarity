#! /usr/bin/env python

import tensorflow as tf
import numpy as np
import os
import time
import datetime
from tensorflow.contrib import learn
from input_helpers import InputHelper
import pandas as pd
# Parameters
# ==================================================
#os.environ["CUDA_VISIBLE_DEVICES"]=""
# Eval Parameters
tf.flags.DEFINE_integer("batch_size", 64, "Batch Size (default: 64)")
tf.flags.DEFINE_string("checkpoint_dir", "", "Checkpoint directory from training run")
tf.flags.DEFINE_string("eval_filepath", "../preprocess_test.csv", "Evaluate on this data (Default: None)")
tf.flags.DEFINE_string("vocab_filepath", "runs/1494995744/checkpoints/vocab", "Load training time vocabulary (Default: None)")
tf.flags.DEFINE_string("model", "runs/1494995744/checkpoints/model-362000", "Load trained model checkpoint (Default: None)")

# Misc Parameters
tf.flags.DEFINE_boolean("allow_soft_placement", True, "Allow device soft device placement")
tf.flags.DEFINE_boolean("log_device_placement", False, "Log placement of ops on devices")


FLAGS = tf.flags.FLAGS
FLAGS._parse_flags()
print("\nParameters:")
for attr, value in sorted(FLAGS.__flags.items()):
    print("{}={}".format(attr.upper(), value))
print("")

if FLAGS.eval_filepath==None or FLAGS.vocab_filepath==None or FLAGS.model==None :
    print("Eval or Vocab filepaths are empty.")
    exit()

# load data and map id-transform based on training time vocabulary
inpH = InputHelper()
x1_test,x2_test,y_test = inpH.getTestDataSet1(FLAGS.eval_filepath, FLAGS.vocab_filepath, 30)

print("\nEvaluating...\n")

# Evaluation
# ==================================================
checkpoint_file = FLAGS.model
print checkpoint_file
graph = tf.Graph()
with graph.as_default():
    session_conf = tf.ConfigProto(
      intra_op_parallelism_threads=15,
      allow_soft_placement=FLAGS.allow_soft_placement,
      log_device_placement=FLAGS.log_device_placement)
    sess = tf.Session(config=session_conf)
    with sess.as_default():
        # Load the saved meta graph and restore variables
        saver = tf.train.import_meta_graph("{}.meta".format(checkpoint_file))
        sess.run(tf.initialize_all_variables())
        saver.restore(sess, checkpoint_file)

        # Get the placeholders from the graph by name
        input_x1 = graph.get_operation_by_name("input_x1").outputs[0]
        input_x2 = graph.get_operation_by_name("input_x2").outputs[0]
        input_y = graph.get_operation_by_name("input_y").outputs[0]

        dropout_keep_prob = graph.get_operation_by_name("dropout_keep_prob").outputs[0]
        # Tensors we want to evaluate
        predictions = graph.get_operation_by_name("output/distance").outputs[0]

        accuracy = graph.get_operation_by_name("accuracy/accuracy").outputs[0]
        #emb = graph.get_operation_by_name("embedding/W").outputs[0]
        #embedded_chars = tf.nn.embedding_lookup(emb,input_x)
        # Generate batches for one epoch
        batches = inpH.batch_iter(list(zip(x1_test,x2_test,y_test)), 2*FLAGS.batch_size, 1, shuffle=False)
        # Collect the predictions here
        all_predictions = []
        all_d=[]
        ground_truth = []
        for db in batches:
            x1_dev_b,x2_dev_b,y_dev_b = zip(*db)
            batch_predictions, batch_acc = sess.run([predictions,accuracy], {input_x1: x1_dev_b, input_x2: x2_dev_b, input_y:y_dev_b, dropout_keep_prob: 1.0})
            all_predictions = np.concatenate([all_predictions, batch_predictions])
            #print(batch_predictions)
            d = np.copy(batch_predictions)
            d[d>=0.5]=999.0
            d[d<0.5]=1
            d[d>1.0]=0
            batch_acc = np.mean(y_dev_b==d)
            all_d = np.concatenate([all_d, d])
            ground_truth = np.concatenate([ground_truth,y_dev_b])
            print("DEV acc {}".format(batch_acc))
            print(len(all_d))
        for ex in all_predictions:
            print ex
        correct_predictions = float(np.mean(all_d == y_test))
        sample_submission = {'test_id' :pd.Series([i for i in range(0,len(all_d))]) ,\
                             'is_duplicate':pd.Series([i for i in all_d]),\
                             'ground_truth':pd.Series(ground_truth)}
        sample_submission = pd.DataFrame(sample_submission)

        sample_submission = sample_submission[['test_id','is_duplicate']]
        sample_submission["is_duplicate"] = sample_submission["is_duplicate"].astype(int)

        sample_submission.to_csv('sample_submission.csv',index=False)
