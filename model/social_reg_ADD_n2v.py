# encoding:utf-8
import sys

sys.path.append("..")
import numpy as np
from mf import MF
from reader.trust import TrustGetter
from utility.matrix import SimMatrix
from utility.similarity_ADD import jaccard
from utility import util

import networkx as nx
from node2vec import Node2Vec

import os

class SocialRegADDn2v(MF):
    """
    docstring for SocialReg

    Ma H, Zhou D, Liu C, et al. Recommender systems with social regularization[C]//Proceedings of the fourth ACM international conference on Web search and data mining. ACM, 2011: 287-296.
    """

    def __init__(self):
        super(SocialRegADDn2v, self).__init__()
        # self.config.lambdaP = 0.001
        # self.config.lambdaQ = 0.001
        self.config.alpha = 0.1
        self.tg = TrustGetter()
        # self.init_model()

    def init_model(self, k):
        super(SocialRegADDn2v, self).init_model(k)
        from collections import defaultdict
        self.user_sim = SimMatrix()
        print('constructing user-user similarity matrix...')

        # for u in self.rg.user:
        #     for f in self.tg.get_followees(u):
        #         if self.user_sim.contains(u, f):
        #             continue
        #         sim = self.get_sim(u, f)
        #         self.user_sim.set(u, f, sim)

        G = nx.Graph()
        for u in self.rg.user:
            for f in self.tg.get_followees(u):
                G.add_edge(u, f)
        
        node2vec = Node2Vec(G, dimensions=64, walk_length=10, num_walks=80, workers=os.cpu_count())
        model = node2vec.fit(window=10, min_count=1, batch_words=4)

        embeddings = model.wv

        for u in self.rg.user:
            for f in self.tg.get_followees(u):
                if self.user_sim.contains(u, f):
                    continue
                sim = embeddings.similarity(str(u), str(f))
                self.user_sim.set(u, f, sim)

    def train_model(self, k):
        super(SocialRegADDn2v, self).train_model(k)
        iteration = 0
        while iteration < self.config.maxIter:
            self.loss = 0
            for index, line in enumerate(self.rg.trainSet()):
                user, item, rating = line
                u = self.rg.user[user]
                i = self.rg.item[item]
                error = rating - self.predict(user, item)
                self.loss += 0.5 * error ** 2
                p, q = self.P[u], self.Q[i]

                social_term_p, social_term_loss = np.zeros((self.config.factor)), 0.0
                followees = self.tg.get_followees(user)
                for followee in followees:
                    if self.rg.containsUser(followee):
                        s = self.user_sim[user][followee]
                        uf = self.P[self.rg.user[followee]]
                        social_term_p += s * (p - uf)
                        social_term_loss += s * ((p - uf).dot(p - uf))

                social_term_m = np.zeros((self.config.factor))
                followers = self.tg.get_followers(user)
                for follower in followers:
                    if self.rg.containsUser(follower):
                        s = self.user_sim[user][follower]
                        ug = self.P[self.rg.user[follower]]
                        social_term_m += s * (p - ug)

                # update latent vectors
                self.P[u] += self.config.lr * (
                        error * q - self.config.alpha * (social_term_p + social_term_m) - self.config.lambdaP * p)
                self.Q[i] += self.config.lr * (error * p - self.config.lambdaQ * q)

                self.loss += 0.5 * self.config.alpha * social_term_loss

            self.loss += 0.5 * self.config.lambdaP * (self.P * self.P).sum() + 0.5 * self.config.lambdaQ * (
                    self.Q * self.Q).sum()

            iteration += 1
            if self.isConverged(iteration):
                break


if __name__ == '__main__':
    # srg = SocialRegADDn2v()
    # srg.train_model(0)
    # coldrmse = srg.predict_model_cold_users()
    # print('cold start user rmse is :' + str(coldrmse))
    # srg.show_rmse()

    rmses = []
    maes = []
    tcsr = SocialRegADDn2v()
    # print(bmf.rg.trainSet_u[1])
    for i in range(tcsr.config.k_fold_num):
        print('the %dth cross validation training' % i)
        tcsr.train_model(i)
        rmse, mae = tcsr.predict_model()
        rmses.append(rmse)
        maes.append(mae)
    rmse_avg = sum(rmses) / 5
    mae_avg = sum(maes) / 5
    print("the rmses are %s" % rmses)
    print("the maes are %s" % maes)
    print("the average of rmses is %s " % rmse_avg)
    print("the average of maes is %s " % mae_avg)
