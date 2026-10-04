"""Shared unweighted and design-weighted statistics for research qualification."""
import numpy as np
from scipy.stats import spearmanr, kendalltau, pearsonr


def correlations(x,y):
    if len(set(x))<2 or len(set(y))<2:
        return dict(spearman=None,kendall_tau_b=None,pearson=None)
    return dict(spearman=float(spearmanr(x,y).statistic),kendall_tau_b=float(kendalltau(x,y).statistic),
                pearson=float(pearsonr(x,y).statistic))

def weighted_corr(x,y,w):
    x,y,w=map(np.asarray,(x,y,w));w=w/w.sum()
    def midrank(a):
        return np.array([sum(w[a<v])+sum(w[a==v])/2 for v in a])
    def corr(a,b):
        a=a-sum(w*a);b=b-sum(w*b)
        denom=np.sqrt(sum(w*a*a)*sum(w*b*b))
        return float(sum(w*a*b)/denom) if denom else None
    num=dx=dy=0.
    for i in range(len(x)):
        for j in range(i):
            sx,sy=np.sign(x[i]-x[j]),np.sign(y[i]-y[j]);wij=w[i]*w[j]
            num+=wij*sx*sy;dx+=wij*(sx!=0);dy+=wij*(sy!=0)
    return dict(spearman=corr(midrank(x),midrank(y)),kendall_tau_b=float(num/np.sqrt(dx*dy)) if dx*dy else None,
                pearson=corr(x,y))
