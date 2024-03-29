import sys
import os
import csv
import collections

import tensorflow as tf
from tensorflow import keras
import numpy as np
import matplotlib
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from scipy import stats
import sklearn.decomposition

os.environ['CUDA_VISIBLE_DEVICES'] = ''

def linreg_model(n_cats):
	ipt = keras.layers.Input(shape = (50,))
	# l1 = keras.layers.Dense(5, activation = 'tanh')(ipt)
	# y = keras.layers.Dense(n_cats, activation = 'softmax', kernel_regularizer = keras.regularizers.l1(.01))(l1)
	y = keras.layers.Dense(n_cats, activation = 'softmax',  kernel_regularizer = keras.regularizers.l1(.01))(ipt)
	model = keras.Model(inputs = ipt, outputs = y)
	return model


def load_embeddings(file, normalize = True):
	word_embs = dict()
	print(f'Loading word embeddings from {file}')
	with open(file) as ein:
		# ein.readline()
		for line in ein:
			lp = line.rstrip('\n ').split(' ')
			word_embs[lp[0]] = np.asarray([float(x) for x in lp[1:]])
			if normalize:
				word_embs[lp[0]] = word_embs[lp[0]] / np.linalg.norm(word_embs[lp[0]])

	return word_embs

def plot_pca(embdict, coloring = True):
	# matplotlib.rc('font', family='FreeSans')
	names = list(embdict.keys())
	
	cmap = dict()
	if coloring:
		header, walsd = load_wals('languages_all_fields.csv', names, startfrom = 6)
		genus = [walsd[x][0] for x in names]
		colors = ['#0F60FF','#02CEE8','#0FFF8E','#14E802','#D1FF0F','#FFDC03','#E89909','#FF6103','#E81809','#FF03D1']
		for l in genus:
			if l not in cmap:
				cmap[l] = colors[len(cmap)]

	mat = np.asarray(list(embdict.values()))
	pca = sklearn.decomposition.PCA(n_components = 2)
	red = pca.fit_transform(mat)
	fig,ax = plt.subplots(figsize = (5,5))
	X = red[:,0]
	Y = red[:,1]
	if coloring:
		ax.scatter(X, Y, c = [cmap[l] for l in genus])
	else:
		ax.scatter(X, Y)
	for i, n in enumerate(names):
		ax.annotate(n, (X[i],Y[i]))
	fig.tight_layout()
	patches = [mpatches.Patch(color = cmap[g], label = g) for g in cmap]
	plt.legend(handles = patches)
	plt.show()



def load_wals(file, langs, discard_threshold = .5, discard_univ = True, startfrom = 10):
	with open(file) as cin:
		creader = csv.reader(cin)
		header = []
		mat = []
		for row in creader:
			if len(header) == 0:
				header = row
			else:
				pr = [(x+' _').split()[0] for x in row]
				if pr[0] in langs:
					# print(pr)
					mat.append(pr)

	mask = [True for i in range(len(header))]
	counts = [0 for i in range(len(header))]
	for j in range(startfrom, len(header)):
		for i in range(len(mat)):
			if mat[i][j] == '_':
				counts[j]+=1
		if discard_univ:
			diff = False
			symb = ''
			for i in range(len(mat)):
				if mat[i][j] == '_':
					continue
				elif symb == '':
					symb = mat[i][j]
				if mat[i][j] != symb:
					diff = True
					break
			if not diff:
				mask[j] = False

	for j in range(len(header)):
		if counts[j] > discard_threshold * len(mat):
			mask[j] = False
	header = np.compress(mask, header)[startfrom:]
	walsd = dict()
	for lang in mat:
		walsd[lang[0]] = np.compress(mask, lang)[startfrom:]

	# print(counts, header, walsd)
	# exit(0)
	return header, walsd

def categoricalize(arr):
	d = dict()
	for k in arr:
		if k not in d:
			d[k] = len(d)

	mat = np.zeros((len(arr), len(d)))
	for i in range(len(arr)):
		mat[i][d[arr[i]]] = 1
	return mat, d

def train_field(embs, y, save_name):
	
	embsmat = list([embs[l] for l in y])
	yarr = list([y[l] for l in y])
	n_cats = len(set(yarr))
	labels, ldict = categoricalize(yarr)
	if len(ldict) < 2:
		print('Warning: attempting to train with only one label. Training skipped.')
		return None, ldict

	model = linreg_model(n_cats)
	optm = keras.optimizers.Adam(lr = 1e-2)
	model.compile(optimizer = optm, loss = 'categorical_crossentropy', metrics = ['categorical_accuracy'])
	data = np.asarray(embsmat)
	model.fit(data, labels, verbose = 1, epochs = 50)

	model.save(save_name+'.h5')

	return model, ldict

def train_all(langembs, wals):
	walsheader, walsmat = load_wals(wals, list(langembs.keys()), .5)
	
	results = []
	for i in range(len(walsheader)):
		keras.backend.clear_session()

		print(f'Dimension {i}')
		lresult = []
		combined = False
		for hol in langembs:
			if walsmat[hol][i] == '_':
				if combined:
					lresult.append(-1)
					continue
				else:
					combined = True
			print('Predicting {}'.format(hol))
			y = dict()
			for l in langembs:
				if l != hol and walsmat[l][i]!='_':
					y[l] = walsmat[l][i]
			if walsmat[hol][i] == '_':
				model, ldict = train_field(langembs, y, 'models/'+walsheader[i].split()[0]+'_combined')
				lresult.append(-1)
			else:
				model, ldict = train_field(langembs, y, 'models/'+walsheader[i].split()[0]+'_'+hol)
				if walsmat[hol][i] in ldict:
					lbl = [x==ldict[walsmat[hol][i]] for x in range(len(ldict))]
					lresult.append(model.evaluate(np.expand_dims(langembs[hol], 0), np.expand_dims(lbl, 0))[1])
				else:
					lresult.append(-2)

		with open(f'models/{walsheader[i].split()[0]}_results.txt', 'w') as fout:
			fout.write(' '.join(langembs.keys())+'\n')
			fout.write(' '.join([str(x) for x in lresult]) + '\n')

		results.append(lresult)
	with open('models/results.csv', 'w') as fout:
		fout.write('lang,'+','.join(['"'+s+'"' for s in walsheader])+'\n')
		results = np.transpose(results)
		for i, l in enumerate(langembs):
			fout.write(l)
			fout.write(','+','.join([str(x) for x in results[i]])+'\n')

def get_baseline(langembs, wals):
	walsheader, walsmat = load_wals(wals, list(langembs.keys()), .5)
	results = []

	for i in range(len(walsheader)):
		cats = [walsmat[l][i] for l in langembs]
		cats = collections.Counter(cats).most_common()
		mf = cats[0][0]
		if mf == '_':
			mf = cats[1][0]
		singletons = []
		for ct in cats:
			if ct[1] == 1 and ct[0] != '_':
				singletons.append(ct[0])
		lresult = []
		for l in langembs:
			if walsmat[l][i] == '_':
				lresult.append(-1)
			elif walsmat[l][i] == mf:
				lresult.append(1)
			elif walsmat[l][i] in singletons:
				lresult.append(-2)
			else:
				lresult.append(0)
		results.append(lresult)

	with open('baseline.csv', 'w') as fout:
		fout.write('lang,'+','.join(['"'+s+'"' for s in walsheader])+'\n')
		results = np.transpose(results)
		for i, l in enumerate(langembs):
			fout.write(l)
			fout.write(','+','.join([str(x) for x in results[i]])+'\n')


if __name__ == '__main__':
	wiki2wals = {'en': 'eng', 'ar': 'ams', 'bg': 'bul', 'ca': 'ctl', 'hr': 'scr', 'cs': 'cze', 'da': 'dsh', 'nl': 'dut', 'et': 'est', 'fi': 'fin', 'fr': 'fre', 'de': 'ger', 'el': 'grk', 'he': 'heb', 'hu': 'hun', 'id': 'ind', 'it': 'ita', 'no': 'nor', 'pl': 'pol', 'pt': 'por', 'ro': 'rom', 'ru': 'rus', 'sk': 'svk', 'sl': 'slo', 'es': 'spa', 'sv': 'swe', 'tr': 'tur', 'uk': 'ukr', 'vi': 'vie'}

	langembs = load_embeddings('seed_lm_2_unk_380k_feat.vec')

	nl = dict()
	for l in wiki2wals:
		if l in langembs:
			nl[wiki2wals[l]] = langembs[l]
	langembs = nl

	train_all(langembs, 'languages_all_fields.csv')
	# get_baseline(langembs, 'languages_all_fields.csv')
	# plot_pca(langembs, True)
