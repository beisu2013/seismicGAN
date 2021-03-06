import time
import numpy as np
import matplotlib.pyplot as plt
import tensorflow as tf


pre_data = np.load('F:/LZB_pre_data/model_6positions_24points.npy')
row_num, col_num, sample_num = np.shape(pre_data)#(700,600,144)
data_num = row_num*col_num
data = np.zeros([data_num, sample_num])
for i in range(row_num):
        trace = pre_data[i,:,:]
        data[(i*col_num):(i*col_num+col_num)] = pre_data[i,:,:]     #三维数据转二维矩阵，采样点数 x 道数

max_val = np.max(data)
min_val = np.min(data)

#异常值：-7.458588736694416e+28
# tmp = data.min(1)
# min_val = -1
# for k in range(data_num):
#     if tmp[k] < min_val and tmp[k] >-70000.0:
#         min_val = tmp[k]

data = (data-min_val)/(max_val-min_val)     #归一化数据

S=[]
for i in range(data.shape[0]):
        S.append(np.reshape(data[i,:],[24,6],))
S = np.asarray(S)
S=S[:, :,: ,np.newaxis]  #（522500,24,6,1）
print('Data shpe = ', S.shape)
###############################################################################################################################


def lrelu(x, th=0.2):
    return tf.maximum(th * x, x)

# G(z)
def generator(x, isTrain=True, reuse=False):
    with tf.variable_scope('generator', reuse=reuse):

        # 1st hidden layer
        conv1 = tf.layers.conv2d_transpose(x, 128, [2, 1], strides=(1, 1), padding='valid')
        lrelu1 = lrelu(tf.layers.batch_normalization(conv1, training=isTrain), 0.2)

        # 2nd hidden layer
        conv2 = tf.layers.conv2d_transpose(lrelu1, 64, [2, 3], strides=(3, 3), padding='same')
        lrelu2 = lrelu(tf.layers.batch_normalization(conv2, training=isTrain), 0.2)

        # 3rd hidden layer
        conv3 = tf.layers.conv2d_transpose(lrelu2, 32, [4, 2], strides=(2, 1), padding='same')
        lrelu3 = lrelu(tf.layers.batch_normalization(conv3, training=isTrain), 0.2)

        # 4rd hidden layer
        conv4 = tf.layers.conv2d_transpose(lrelu3, 16, [3, 3], strides=(1, 2), padding='same')
        lrelu4 = lrelu(tf.layers.batch_normalization(conv4, training=isTrain), 0.2)

        # output layer
        conv5 = tf.layers.conv2d_transpose(lrelu4, 1, [3, 3], strides=(2, 1), padding='same')
        o = tf.nn.tanh(conv5)

        return o

# D(x)
def discriminator(x, isTrain=True, reuse=False):
    with tf.variable_scope('discriminator', reuse=reuse):
        # 1st hidden layer
        conv1 = tf.layers.conv2d(x, 16, [3, 3], strides=(2, 1), padding='same')
        lrelu1 = lrelu(conv1, 0.2)

        # 2nd hidden layer
        conv2 = tf.layers.conv2d(lrelu1, 32, [3, 3], strides=(1, 2), padding='same')
        lrelu2 = lrelu(tf.layers.batch_normalization(conv2, training=isTrain), 0.2)

        # 3nd hidden layer
        conv3 = tf.layers.conv2d(lrelu2, 64, [4, 2], strides=(2, 1), padding='same')
        lrelu3 = lrelu(tf.layers.batch_normalization(conv3, training=isTrain), 0.2)

        # 4rd hidden layer
        conv4 = tf.layers.conv2d(lrelu3, 128, [2, 3], strides=(3, 3), padding='same')

        # feature extract
        fea = conv4
        pool_conv2 = tf.layers.max_pooling2d(inputs=conv2, pool_size=[3, 3], strides=[6,3], padding='same')
        tf.concat([fea, pool_conv2], 3)
        fea = tf.layers.conv2d(fea, 64, [1,1], strides=(1, 1), padding='same')
        lrelu4 = lrelu(tf.layers.batch_normalization(fea, training=isTrain), 0.2)

        # output layer
        conv5 = tf.layers.conv2d(lrelu4, 1, [2, 1], strides=(1, 1), padding='valid')
        o = tf.nn.sigmoid(conv5)

        return o, conv5, fea

# training paramet
batch_size = 100
lr = 0.0002
train_epoch = 10

# variables : input
x = tf.placeholder(tf.float32, shape=(None, 24, 6, 1))
z = tf.placeholder(tf.float32, shape=(None, 1, 1, 50))
isTrain = tf.placeholder(dtype=tf.bool)

# networks : generator
G_z = generator(z, isTrain)

# networks : discriminator
D_real, D_real_logits, D_real_feature= discriminator(x, isTrain)
D_fake, D_fake_logits, _ = discriminator(G_z, isTrain, reuse=True)

# loss for each network
D_loss_real = tf.reduce_mean(tf.nn.sigmoid_cross_entropy_with_logits(logits=D_real_logits, labels=tf.ones([batch_size, 1, 1, 1])))
D_loss_fake = tf.reduce_mean(tf.nn.sigmoid_cross_entropy_with_logits(logits=D_fake_logits, labels=tf.zeros([batch_size, 1, 1, 1])))
D_loss = D_loss_real + D_loss_fake
G_loss = tf.reduce_mean(tf.nn.sigmoid_cross_entropy_with_logits(logits=D_fake_logits, labels=tf.ones([batch_size, 1, 1, 1])))

# trainable variables for each network
T_vars = tf.trainable_variables()
D_vars = [var for var in T_vars if var.name.startswith('discriminator')]
G_vars = [var for var in T_vars if var.name.startswith('generator')]

# optimizer for each network
with tf.control_dependencies(tf.get_collection(tf.GraphKeys.UPDATE_OPS)):
    D_optim = tf.train.AdamOptimizer(lr, beta1=0.5).minimize(D_loss, var_list=D_vars)
    G_optim = tf.train.AdamOptimizer(lr, beta1=0.5).minimize(G_loss, var_list=G_vars)

# open session and initialize all variables
sess = tf.InteractiveSession()
tf.global_variables_initializer().run()


train_hist = {}
train_hist['D_losses'] = []
train_hist['G_losses'] = []
train_hist['per_epoch_ptimes'] = []
train_hist['total_ptime'] = []

# training-loop
np.random.seed(int(time.time()))
print('training start!')
start_time = time.time()

G_losses = []
D_losses = []
epoch_start_time = time.time()
saver=tf.train.Saver(max_to_keep=1)
for iter in range(S.shape[0] // batch_size):
    # update discriminator
    x_ = S[iter*batch_size:(iter+1)*batch_size]
    z_ = np.random.normal(0, 1, (batch_size, 1, 1, 50))

    loss_d_, _ = sess.run([D_loss, D_optim], {x: x_, z: z_, isTrain: True})
    D_losses.append(loss_d_)

    # update generator
    z_ = np.random.normal(0, 1, (batch_size, 1, 1, 50))
    loss_g_, _ = sess.run([G_loss, G_optim], {z: z_, x: x_, isTrain: True})
    G_losses.append(loss_g_)

    if iter % 209 == 0:
        saver.save(sess, 'ckpt/LZB_DCGAN128_FeatureFusion3.ckpt', global_step=iter + 1)
    epoch_end_time = time.time()
    per_epoch_ptime = epoch_end_time - epoch_start_time
    print('[%d] - ptime: %.2f loss_d: %.3f, loss_g: %.3f' % ((iter + 1), per_epoch_ptime, np.mean(D_losses), np.mean(G_losses)))

    train_hist['D_losses'].append(np.mean(D_losses))
    train_hist['G_losses'].append(np.mean(G_losses))
    train_hist['per_epoch_ptimes'].append(per_epoch_ptime)

end_time = time.time()
total_ptime = end_time - start_time
train_hist['total_ptime'].append(total_ptime)

print('Avg per epoch ptime: %.2f, total %d epochs ptime: %.2f' % (np.mean(train_hist['per_epoch_ptimes']), train_epoch, total_ptime))
print("Training finish!")

###########################################################################################################################

print("Start saving features")
Flat_feat = np.zeros([data_num, 128])
for ii in range(S.shape[0] //batch_size):
    X = S[ii*batch_size:(ii+1)*batch_size]    #不降维切块
    Feat = sess.run(D_real_feature, {x: X, isTrain: False})
    Flat_feat[ii*batch_size:(ii+1)*batch_size] = np.reshape(Feat, [batch_size,-1])
    print(ii)
features = Flat_feat
np.save('model_features_DCGANL5_FF.npy', features)

############################################################################################################################

print("start cluster")
n_clusters = 6
print("Learning the clusters.")
from sklearn.cluster import KMeans
kmeans = KMeans(n_clusters=n_clusters, init='k-means++').fit(features)
print("Extracting features from val set and predicting from it.")
pred_labels_kmeans = kmeans.predict(features)

result = np.reshape(pred_labels_kmeans,[row_num, col_num])
np.save('model_result_FF.npy', result)
plt.imshow(result)
plt.show()
sess.close()
# seismicGAN
