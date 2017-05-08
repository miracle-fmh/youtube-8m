# Copyright 2016 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Provides definitions for non-regularized training or test losses."""

import tensorflow as tf
from tensorflow import flags
import numpy as np
FLAGS = flags.FLAGS
flags.DEFINE_integer(
  "num_pairs", 10,
  "The number of pairs (excluding the dummy 'expert') used for Hingeloss.")
flags.DEFINE_string("class_file", "./resources/labels_knowledge.out",
                    "The directory to save the model files in.")
flags.DEFINE_string("frequent_file", "./resources/labels_frequent.out",
                    "The directory to save the model files in.")
flags.DEFINE_string("autoencoder_dir", "./resources/",
                    "The directory to save the model files in.")
flags.DEFINE_string("support_type", None,
                    "The directory to save the model files in.")
flags.DEFINE_string("loss_function", None,
                    "The directory to save the model files in.")
flags.DEFINE_integer("encoder_layers", 2,
                    "The number of mixtures (excluding the dummy 'expert') used for MoeModel.")
flags.DEFINE_float("jsd_pi", 0.5,
                   "Which learning rate to start with.")
flags.DEFINE_float("threshold", 0.5,
                   "Which learning rate to start with.")

class BaseLoss(object):
  """Inherit from this class when implementing new losses."""

  def calculate_loss(self, unused_predictions, unused_labels, **unused_params):
    """Calculates the average loss of the examples in a mini-batch.

     Args:
      unused_predictions: a 2-d tensor storing the prediction scores, in which
        each row represents a sample in the mini-batch and each column
        represents a class.
      unused_labels: a 2-d tensor storing the labels, which has the same shape
        as the unused_predictions. The labels must be in the range of 0 and 1.
      unused_params: loss specific parameters.

    Returns:
      A scalar loss tensor.
    """
    raise NotImplementedError()

class CrossEntropyLoss(BaseLoss):
  """Calculate the cross entropy loss between the predictions and labels.
  """
  def calculate_loss(self, predictions, labels, **unused_params):
    with tf.name_scope("loss_xent"):
      epsilon = 10e-6
      float_labels = tf.cast(labels, tf.float32)
      margin_loss = 0.0
      if FLAGS.loss_function=="loss_square":
        print("loss_square")
        predictions = predictions*predictions
        cross_entropy_loss = float_labels * tf.log(predictions + epsilon) + (
            1 - float_labels) * tf.log(1 - predictions + epsilon)
      elif FLAGS.loss_function=="loss_sqrt":
        print("loss_sqrt")
        predictions = tf.sqrt(predictions)
        cross_entropy_loss = float_labels * tf.log(predictions + epsilon) + (
            1 - float_labels) * tf.log(1 - predictions + epsilon)
      elif FLAGS.loss_function=="loss_jsd":
        print("loss_jsd")
        alpha = FLAGS.jsd_pi
        jsd_dis = (1-alpha)*float_labels+alpha*predictions
        cross_entropy_loss_1 = (1-alpha)*predictions * tf.log(jsd_dis + epsilon) + (1-alpha)*(
          1 - predictions) * tf.log(1 - jsd_dis + epsilon) + alpha*float_labels * tf.log(jsd_dis + epsilon) + alpha*(
          1 - float_labels) * tf.log(1 - jsd_dis + epsilon)
        cross_entropy_loss_2 = (1-alpha)*predictions * tf.log(predictions + epsilon) + (1-alpha)*(
          1 - predictions) * tf.log(1 - predictions + epsilon)
        cross_entropy_loss = cross_entropy_loss_1 - cross_entropy_loss_2
      elif FLAGS.loss_function=="loss_mix":
        print("loss_mix")
        cross_entropy_loss_1 = float_labels * tf.log(predictions + epsilon) + (
            1 - float_labels) * tf.log(1 - predictions + epsilon)
        cross_entropy_loss_2 = predictions * tf.log(float_labels + epsilon) + (
            1 - predictions) * tf.log(1 - float_labels + epsilon)
        cross_entropy_loss_3 = predictions * tf.log(predictions + epsilon) + (
            1 - predictions) * tf.log(1 - predictions + epsilon)
        cross_entropy_loss = cross_entropy_loss_1 + cross_entropy_loss_2 - cross_entropy_loss_3
      elif FLAGS.loss_function=="loss_weight":
        print("loss_weight")
        seq = np.loadtxt(FLAGS.class_file)
        vocab_size = seq.shape[0]
        labels_size = float_labels.get_shape().as_list()[1]
        if labels_size>vocab_size:
          seq = np.tile(seq,[labels_size//vocab_size,1])
        tf_seq = tf.constant(seq,dtype=tf.float32)
        tf_seq_transpose = tf.transpose(tf_seq)
        class_labels = tf.matmul(float_labels,tf_seq)
        class_labels = tf.clip_by_value(class_labels,0.0,1.0)
        class_labels = tf.matmul(class_labels,tf_seq_transpose)
        modify_labels = 1.0 - tf.clip_by_value(class_labels,0.0,0.5)
        cross_entropy_loss = float_labels * tf.log(predictions + epsilon) + (
            1 - float_labels) * tf.log(1 - predictions + epsilon)*modify_labels

      elif FLAGS.loss_function=="loss_margin":
        print("loss_margin")

        predictions_pos = tf.reduce_sum(predictions*(0.5-tf.log(predictions + epsilon))*float_labels)\
                          /tf.reduce_sum((0.5-tf.log(predictions + epsilon))*float_labels)*tf.reduce_mean(tf.reduce_sum(float_labels,1))
        predictions_neg = tf.reduce_sum(predictions*(0.5-tf.log(1-predictions + epsilon))*(1-float_labels))\
                          /tf.reduce_sum((1-float_labels)*(0.5-tf.log(1-predictions + epsilon)))*tf.reduce_mean(tf.reduce_sum(1-float_labels,1))
        margin_loss = tf.negative(predictions_pos-predictions_neg)

        cross_entropy_loss = float_labels * tf.log(predictions + epsilon) + (
            1 - float_labels) * tf.log(1 - predictions + epsilon)

      elif FLAGS.loss_function=="loss_delete":
        print("loss_delete")

        cross_entropy_loss = float_labels * tf.log(predictions + epsilon) + (
            1 - float_labels) * tf.log(1 - predictions + epsilon)
        batch_size = tf.cast(tf.shape(predictions)[0],dtype=tf.float32)
        vocab_size = tf.cast(tf.shape(predictions)[1],dtype=tf.float32)
        topk_num = tf.cast(batch_size*vocab_size*0.0001,dtype=tf.int32)
        cross_entropy_loss = tf.reshape(tf.negative(cross_entropy_loss),[1,-1])
        margin_loss,_ = tf.nn.top_k(cross_entropy_loss,k=topk_num)
        margin_loss = (tf.reduce_sum(cross_entropy_loss)-tf.reduce_sum(margin_loss))/batch_size

        cross_entropy_loss = cross_entropy_loss*0.0

      else:
        cross_entropy_loss = float_labels * tf.log(predictions + epsilon) + (
            1 - float_labels) * tf.log(1 - predictions + epsilon)

      cross_entropy_loss = tf.negative(cross_entropy_loss)

      return tf.reduce_mean(tf.reduce_sum(cross_entropy_loss, 1)) + margin_loss

  def calculate_loss_negative(self, predictions_pos, predictions_neg, labels, **unused_params):
    with tf.name_scope("loss_negative"):
      epsilon = 10e-6
      float_labels = tf.cast(labels, tf.float32)
      weight_pos = np.loadtxt(FLAGS.autoencoder_dir+"labels_uni.out")
      weight_pos = tf.reshape(tf.cast(weight_pos,dtype=tf.float32),[1,-1])
      weight_pos = tf.log(tf.reduce_max(weight_pos)/weight_pos)+1
      cross_entropy_loss_1 = float_labels * tf.log(predictions_pos + epsilon)*weight_pos + (
          1 - float_labels) * tf.log(1 - predictions_pos + epsilon)
      cross_entropy_loss_2 = (1-float_labels) * tf.log(predictions_neg + epsilon) + \
                             float_labels * tf.log(1 - predictions_neg + epsilon)
      cross_entropy_loss = tf.negative(cross_entropy_loss_1+cross_entropy_loss_2)
      return tf.reduce_mean(tf.reduce_sum(cross_entropy_loss, 1))

  def calculate_mseloss(self, predictions, labels, **unused_params):
    with tf.name_scope("loss_mse"):
      float_labels = tf.cast(labels, tf.float32)
      mse_loss = tf.square(predictions-float_labels)
      return tf.reduce_mean(tf.reduce_sum(mse_loss, 1))

  def calculate_loss_postprocess(self, predictions, labels, **unused_params):
    with tf.name_scope("loss_postprocess"):
      float_labels = tf.cast(labels, tf.float32)
      predictions_pos = predictions*float_labels + (1-float_labels)
      predictions_neg = predictions*(1-float_labels)
      min_pos = tf.stop_gradient(tf.reduce_min(predictions_pos))
      max_neg = tf.stop_gradient(tf.reduce_max(predictions_neg))
      predictions_pos_mistake = tf.nn.relu(max_neg-predictions_pos)-0.01*tf.nn.relu(predictions_pos-max_neg)
      predictions_neg_mistake = tf.nn.relu(predictions_neg-min_pos)-0.01*tf.nn.relu(min_pos-predictions_neg)
      postprocess_loss = predictions_pos_mistake + predictions_neg_mistake
      return tf.reduce_mean(tf.reduce_sum(postprocess_loss, 1))

  def calculate_loss_max(self, predictions, predictions_experts, labels, **unused_params):
    with tf.name_scope("loss_max"):
      epsilon = 10e-6
      shape = predictions_experts.get_shape().as_list()
      float_labels = tf.cast(labels, tf.float32)
      cross_entropy_loss = float_labels * tf.log(predictions + epsilon) + (
                        1 - float_labels) * tf.log(1 - predictions + epsilon)
      float_exprts = tf.tile(tf.reshape(float_labels,[-1,shape[1],1]),[1,1,shape[2]])
      cross_entropy_experts = float_exprts * tf.log(predictions_experts + epsilon) + (
                     1 - float_exprts) * tf.log(1 - predictions_experts + epsilon)
      cross_entropy_loss = tf.negative(cross_entropy_loss)
      cross_entropy_experts = tf.negative(tf.reduce_mean(cross_entropy_experts,axis=2))
      return tf.reduce_mean(tf.reduce_sum(cross_entropy_loss, 1)) + tf.reduce_mean(tf.reduce_sum(cross_entropy_experts, 1))

  def calculate_loss_mix(self, predictions, predictions_class, labels, **unused_params):
    with tf.name_scope("loss_mix"):
      float_labels = tf.cast(labels, tf.float32)
      if FLAGS.support_type=="class":
        seq = np.loadtxt(FLAGS.class_file)
        tf_seq = tf.one_hot(tf.constant(seq,dtype=tf.int32),FLAGS.encoder_size)
        float_classes_org = tf.matmul(float_labels,tf_seq)
        class_true = tf.ones(tf.shape(float_classes_org))
        class_false = tf.zeros(tf.shape(float_classes_org))
        float_classes = tf.where(tf.greater(float_classes_org, class_false), class_true, class_false)
        cross_entropy_class = self.calculate_loss(predictions_class,float_classes)
      elif FLAGS.support_type=="frequent":
        float_classes = float_labels[:,0:FLAGS.encoder_size]
        cross_entropy_class = self.calculate_loss(predictions_class,float_classes)
      elif FLAGS.support_type=="encoder":
        float_classes = float_labels
        for i in range(FLAGS.encoder_layers):
          var_i = np.loadtxt(FLAGS.autoencoder_dir+'autoencoder_layer%d.model' % i)
          weight_i = tf.constant(var_i[:-1,:],dtype=tf.float32)
          bias_i = tf.reshape(tf.constant(var_i[-1,:],dtype=tf.float32),[-1])
          float_classes = tf.nn.xw_plus_b(float_classes,weight_i,bias_i)
          if i<FLAGS.encoder_layers-1:
            float_classes = tf.nn.relu(float_classes)
          else:
            float_classes = tf.nn.sigmoid(float_classes)
            #float_classes = tf.nn.relu(tf.sign(float_classes - 0.5))
        cross_entropy_class = self.calculate_mseloss(predictions_class,float_classes)
      else:
        float_classes = float_labels
        for i in range(FLAGS.moe_layers-1):
          float_classes = tf.concat((float_classes,float_labels),axis=1)
        cross_entropy_class = self.calculate_loss(predictions_class,float_classes)
      cross_entropy_loss = self.calculate_loss(predictions,labels)
      return cross_entropy_loss + 0.1*cross_entropy_class

  def calculate_loss_mix2(self, predictions, predictions_class, predictions_encoder, labels, **unused_params):
    with tf.name_scope("loss_mix2"):
      float_labels = tf.cast(labels, tf.float32)
      float_encoders = float_labels
      for i in range(FLAGS.encoder_layers):
        var_i = np.loadtxt(FLAGS.autoencoder_dir+'autoencoder_layer%d.model' % i)
        weight_i = tf.constant(var_i[:-1,:],dtype=tf.float32)
        bias_i = tf.reshape(tf.constant(var_i[-1,:],dtype=tf.float32),[-1])
        float_encoders = tf.nn.xw_plus_b(float_encoders,weight_i,bias_i)
        if i<FLAGS.encoder_layers-1:
          float_encoders = tf.nn.relu(float_encoders)
        else:
          hidden_mean = tf.reduce_mean(float_encoders,axis=1,keep_dims=True)
          hidden_std = tf.sqrt(tf.reduce_mean(tf.square(float_encoders-hidden_mean),axis=1,keep_dims=True))
          float_encoders = (float_encoders-hidden_mean)/(hidden_std+1e-6)
          #float_encoders = tf.nn.sigmoid(float_encoders)
      cross_entropy_encoder = 0.1*self.calculate_mseloss(predictions_encoder,float_encoders)
      cross_entropy_loss = self.calculate_loss(predictions,labels)
      return cross_entropy_encoder+cross_entropy_loss, float_encoders
      #return cross_entropy_encoder, float_encoders

class CrossEntropyLoss_weight(BaseLoss):
  """Calculate the cross entropy loss between the predictions and labels.
  """

  def calculate_loss(self, predictions, labels, **unused_params):
    with tf.name_scope("loss_xent"):
      epsilon = 10e-6
      vocab_size = predictions.get_shape().as_list()[1]
      float_labels = tf.cast(labels, tf.float32)
      cross_entropy_loss = float_labels * tf.log(predictions + epsilon) + (
          1 - float_labels) * tf.log(1 - predictions + epsilon)
      cross_entropy_loss = tf.negative(cross_entropy_loss)
      neg_labels = 1 - float_labels
      predictions_pos = predictions*float_labels+10*neg_labels
      predictions_minpos = tf.reduce_min(predictions_pos,axis=1,keep_dims=True)
      predictions_neg = predictions*neg_labels-10*float_labels
      predictions_maxneg = tf.reduce_max(predictions_neg,axis=1,keep_dims=True)
      mask_1 = tf.cast(tf.greater_equal(predictions_neg, predictions_minpos),dtype=tf.float32)
      mask_2 = tf.cast(tf.less_equal(predictions_pos, predictions_maxneg),dtype=tf.float32)
      cross_entropy_loss = cross_entropy_loss*(mask_1+mask_2)*10 + cross_entropy_loss
      return tf.reduce_mean(tf.reduce_sum(cross_entropy_loss, 1))


class HingeLoss_cos(BaseLoss):
  """Calculate the hinge loss between the predictions and labels.

  Note the subgradient is used in the backpropagation, and thus the optimization
  may converge slower. The predictions trained by the hinge loss are between -1
  and +1.
  """
  def calculate_loss(self, predictions, labels, b1=1.6, b2=-0.4, **unused_params):
    with tf.name_scope("loss_hinge"):
      float_labels = tf.cast(labels, tf.float32)
      neg_labels = 1 - float_labels
      shape = predictions.get_shape().as_list()[1]
      all_zeros = tf.zeros([FLAGS.batch_size,shape,FLAGS.num_pairs], dtype=tf.float32)

      """
      predictions_minpos = predictions*float_labels+10*neg_labels
      predictions_minpos = tf.reduce_min(predictions_minpos,axis=1,keep_dims=True)
      predictions_maxneg = predictions*neg_labels-10*float_labels
      mask_1 = tf.cast(tf.greater_equal(predictions_maxneg, predictions_minpos),dtype=tf.float32)
      mask_2 = neg_labels
      pos_indices = []
      for i in range(FLAGS.batch_size):
        pos_var = tf.where(tf.not_equal(float_labels[i,:],all_zeros[i,:]))
        pos_indice = tf.tile(tf.reshape(pos_var[:,0],[-1]),[shape])+i*shape
        pos_indice = pos_indice[0:shape]
        rand_var = tf.random_uniform([shape],0,shape, dtype=tf.int32)
        pos_indice = tf.gather(pos_indice,rand_var)
        pos_indices.append(pos_indice)

      pos_indices = tf.reshape(tf.stack(pos_indices,axis=0), [-1])

      predictions_shuffle = tf.reshape(tf.gather(tf.reshape(predictions, [-1]),pos_indices), [-1,shape])
      hinge_loss = tf.maximum(all_zeros, b1 - predictions_shuffle + predictions)
      hinge_loss = hinge_loss*mask_1 + hinge_loss*mask_2
      return tf.reduce_mean(tf.reduce_sum(hinge_loss,axis=1))"""

      predictions_shuffles = []
      predictions_pos = tf.reshape(predictions*float_labels+(2-predictions)*neg_labels,[-1,shape,1])
      predictions_neg = predictions*neg_labels+(2-predictions)*float_labels
      predictions_org = tf.reshape(predictions,[-1,shape,1])
      for i in range(FLAGS.num_pairs):
        rand_var = tf.random_uniform([FLAGS.batch_size, shape],0,shape, dtype=tf.int32)+tf.reshape(tf.range(0, FLAGS.batch_size) * shape,[FLAGS.batch_size,1])
        neg_indice = tf.reshape(rand_var, [-1])
        predictions_shuffle = tf.reshape(tf.gather(tf.reshape(predictions_neg,[-1]),neg_indice),[-1,shape])
        predictions_shuffles.append(tf.reshape(predictions_shuffle,[-1,shape]))

      predictions_shuffles = tf.stack(predictions_shuffles,axis=2)

      const = tf.reshape(b1*float_labels+b2*neg_labels,[-1,shape,1])
      hinge_loss = tf.maximum(all_zeros, b1 - predictions_pos + predictions_shuffles)
      return tf.reduce_mean(tf.reduce_sum(hinge_loss,axis=1))


class SoftmaxLoss(BaseLoss):
  """Calculate the softmax loss between the predictions and labels.

  The function calculates the loss in the following way: first we feed the
  predictions to the softmax activation function and then we calculate
  the minus linear dot product between the logged softmax activations and the
  normalized ground truth label.

  It is an extension to the one-hot label. It allows for more than one positive
  labels for each sample.
  """

  def calculate_loss(self, predictions, labels, **unused_params):
    bound = FLAGS.softmax_bound
    vocab_size_1 = bound
    with tf.name_scope("loss_softmax"):
      epsilon = 10e-8
      float_labels = tf.cast(labels, tf.float32)
      labels_1 = float_labels[:,:vocab_size_1]
      predictions_1 = predictions[:,:vocab_size_1]
      cross_entropy_loss = CrossEntropyLoss().calculate_loss(predictions_1,labels_1)
      lables_2 = float_labels[:,vocab_size_1:]
      predictions_2 = predictions[:,vocab_size_1:]
      # l1 normalization (labels are no less than 0)
      label_rowsum = tf.maximum(
          tf.reduce_sum(lables_2, 1, keep_dims=True),
          epsilon)
      label_append = 1.0-tf.reduce_max(lables_2, 1, keep_dims=True)
      norm_float_labels = tf.concat((tf.div(lables_2, label_rowsum),label_append),axis=1)
      predictions_append = 1.0-tf.reduce_sum(predictions_2, 1, keep_dims=True)
      softmax_outputs = tf.concat((predictions_2,predictions_append),axis=1)
      softmax_loss = norm_float_labels * tf.log(softmax_outputs + epsilon) + (
          1 - norm_float_labels) * tf.log(1 - softmax_outputs + epsilon)
      softmax_loss = tf.negative(tf.reduce_sum(softmax_loss, 1))
    return tf.reduce_mean(softmax_loss) + cross_entropy_loss

  def calculate_loss_mix(self, predictions, predictions_class, labels, **unused_params):
    with tf.name_scope("loss_softmax_mix"):
      vocab_size = labels.get_shape().as_list()[1]
      cross_entropy_class = tf.constant(0.0)
      for i in range(FLAGS.moe_layers):
        predictions_subclass = predictions_class[:,i*vocab_size:(i+1)*vocab_size]
        cross_entropy_class = cross_entropy_class + self.calculate_loss(predictions_subclass,labels)
      cross_entropy_loss = self.calculate_loss(predictions,labels)
      return cross_entropy_loss + 0.1*cross_entropy_class
