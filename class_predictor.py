

# класс, присваивающий каждому sku категорию: картон, пластик, без упаковки или стретч
# на вход необходимо подать 2 модели: для классификации больших предметов
# и для классификации малых предметов.
# также надо подать данные из файла full_sku_data.csv и carton_full_features.csv

import pandas as pd

import numpy as np



class predictor:
    def __init__(self, model_large=np.nan, model_small=np.nan, sku=np.nan, carton=np.nan):
        self.model_large = model_large
        self.model_small = model_small
        self.sku = sku
        self.carton = carton
    
    def large_assignment(self, value):
        if value==0:
            return 'nonpack'
        else:
            return 'stretch'
    
    def small_assignment(self, value):
        if value==0:
            return 'plastic'
        else:
            return 'box'
    
    
    def predict(self, query):
        try:
            self.sku = self.sku.set_index('sku')
        except:
            pass
        
        self.df = pd.DataFrame(query, columns=['sku']).join(self.sku, on='sku', how='left')
        self.features_large = self.df[(self.df['a'] > self.carton['max_diag'].max())
                                     |(self.df['volume'] > self.carton['volume'].max())]
        self.features_small = self.df[(self.df['a'] <= self.carton['max_diag'].max())
                                     & (self.df['volume'] < self.carton['volume'].max())]
        if self.features_large.shape[0]>0:
            self.features_large.loc[:,'prediction'] = self.model_large.predict(self.features_large.loc[:, 'a':'category_14.0'])
            self.features_large['prediction'] = self.features_large['prediction'].apply(self.large_assignment)
        
        if self.features_small.shape[0]>0:
            self.features_small.loc[:,'prediction'] = self.model_small.predict(self.features_small.loc[:, 'a':'category_14.0'])
            self.features_small['prediction'] = self.features_small['prediction'].apply(self.small_assignment)
        
        return pd.concat([self.features_large, self.features_small])

