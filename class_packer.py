
import pandas as pd

import numpy as np



class packer:
    def __init__(self, predictions, carton):
        
        # в классе мы сохраняем таблицу упаковок
        # и предсказания, полученные на предыдущей стадии.
        
        # добавляем в предсказания столбец 'packed', чтоб отмечать, какие товары уже упакованы.
        # товары в пленке и без упаковки сразу же помечаем как упакованные - к ним подбирать коробку не надо.
        # сортируем полученную таблицу сперва в порядке "упакованности", затем в порядке предсказанного вида упаковки,
        # затем по объему и наконец по длине - это пригодится для процесса упаковки.
        
        
        self.carton = carton
        self.pred = predictions
        self.pred.loc[:,'packed'] = False
        self.pred.loc[self.pred.loc[:,'prediction'].isin(['nonpack', 'stretch']),'packed'] = True
        self.pred = self.pred.sort_values(by=['packed', 'prediction', 'volume', 'a'], ascending=False)
        self.pred = self.pred.reset_index(drop=True)
        
        
        
        # обрабатываем случай, когда предмет длинее диагонали самого большого пакета, но получил на предыдущей стадии предсказание
        # "plastic": меняем значение на 'box'
        
        # в случае если данные по carton изменятся, 'plastic' и 'box' поменяются местами в зависимости от того, 
        # упаковка какого класса больше.
        
        if self.carton[self.carton['type']=='plastic']['max_diag'].max() > self.carton[self.carton['type']=='box']['max_diag'].max():
            self.b = 'box'
            self.a = 'plastic'
        else:
            self.b = 'plastic'
            self.a = 'box'
        
        self.pred.loc[(self.pred['prediction']==self.b)
                      & (self.pred['a'] > self.carton[self.carton['type']==self.b]['max_diag'].max()), 'prediction'] = self.a

        
        
        # повторяем процедуру, но в этот раз с объемом.
        # товары, не влезающие по объему в пластиковый пакетик, пойдут в коробки.
        
        if self.carton[self.carton['type']=='plastic']['volume'].max() > self.carton[self.carton['type']=='box']['volume'].max():
            self.b = 'box'
            self.a = 'plastic'
        else:
            self.b = 'plastic'
            self.a = 'box'
        
        self.pred.loc[(self.pred['prediction']==self.b)
                      & (self.pred['volume'] > self.carton[self.carton['type']==self.b]['volume'].max()), 'prediction'] = self.a
        
    # теперь можно упаковывать!
   # Сперва пишем функцию для того, чтоб в выводе основного метода была информация по нонпакам и стретчам 
    def assign_nonpacks(self, row):
        if row['prediction'] in ['stretch', 'nonpack']:
            self.box_list.append(row['prediction'])
            self.type_list.append('_none')
            self.sku_list.append([row['sku']])
    
  # теперь пишем основной метод  
    def pack(self):
        self.box_list = [] # здесь будем сохранять список коробок для результирующего датафрейма
        self.sku_list = [] # здесь будут вложены списки sku, по одному на коробку
        self.type_list = [] # здесь будет тип коробки
        
        
        self.pred.apply(self.assign_nonpacks, axis=1) # вызываем функцию, которая добавит в вывод нонпаки и стретчи

        
        
        # ниже начинается ПЕРВЫЙ цикл while. Он продолжится, пока не все предметы упакованы
        
        
        while len(self.pred['packed']) > sum(self.pred['packed']):
            for x in ['box', 'plastic']: 
                
                
                # выполняем одни и те же действия над предметами, подходящими для коробок и для предметами, подходящими для пакетов
                # обрабатывать в цикле будем два разных случая:
                #
                # 1 - когда все предметы класса х поместятся в одну коробку класса х
                #
                # 2 - когда все предметы класса х не поместятся в одну коробку класса х
                #
                # начнем со случая, когда все предметы класса х помещаются в одну коробку класса х, см ниже.
                
                if x in self.pred.loc[self.pred['packed']==False, 'prediction'].values:
                    
                    # 'если не все предметы из класса х еще упакованы И
                    # если все предметы класса х влезут в одну упаковку класса х'
                    if self.pred.loc[(self.pred['packed']==False) & (self.pred['prediction']==x), 'volume'].sum() < \
                    self.carton[self.carton['type']==x]['volume'].max():
                        
                                                
                        # добавляем в список коробок самую дешевую коробку, в которую влезут все товары
                        self.box_list.append(
                            self.carton[(self.carton['type']==x) & \
                            (self.carton['max_diag'] >= \
                             self.pred.loc[(self.pred['packed']==False) & \
                                           (self.pred['prediction']==x), 'a'].max()) & \
                                        (self.carton['volume'] >= self.pred.loc[(self.pred['packed']==False) & \
                                           (self.pred['prediction']==x), 'volume'].sum())
                                       ].sort_values(by='price').head(1)['name'].values[0])
                        
                        # добавляем в список sku вложенный список со всеми sku, которые влезли в коробку
                        
                        self.sku_list.append(self.pred.loc[(self.pred['packed']==False) & (self.pred['prediction']==x)]['sku'].values)
                        
                        # добавляем класс упаковки в список классов упаковки
                        
                        self.type_list.append(x)
                        
                        # исправляем статус погруженных в коробку sku на "упакованы"
                        self.pred.loc[(self.pred['packed']==False) & (self.pred['prediction']==x),'packed'] = True
        

            # Обрабатываем второй случай: не все предметы класса х помещаются в одну коробку класса х.
            #
            # для этого планируются следующие мероприятия:
            # 1. выбираем самую большую коробку подходящего класса
            # 2. в нее запихиваем самый большой предмет этого класса
            # 3. из объема коробки вычитаем объем предмета
            # 4. далее во втором цикле while заполняем коробку вторым предметом
            # повторяется цикл до тех пор, пока самый маленький предмет в таблице перестанет помещаться в эту коробку.
            # после этого происходит выход из внутреннего цикла while
            #
                    else: 
                        if x in self.pred.loc[self.pred['packed']==False, 'prediction'].values:
                
                
                # в этой строке выбираем самую большую коробку и записываем ее имя и объем в список self.box
                            self.box = ['name', 0]
                            self.id = self.carton.loc[self.carton['type']==x, 'volume'].idxmax()
                            self.box[0] = self.carton.loc[self.id, 'name']
                            self.box[1] = self.carton.loc[self.id, 'volume']

                    
                    
                    
                
                # создаем пустой список, куда пойдут предметы, оказавшиеся в коробке
                            self.list_of_items_in_box = []
                
                # вложенный цикл while: продолжаться будет до тех пор, пока оставшийся объем коробки превышает объем самого малого предмета
                # подходящего класса
                            while self.box[1] > self.pred.loc[(self.pred['packed']==False)
                                                     & (self.pred['prediction']==x),'volume'].min():
                
                
                
                    # в self_id сохраняем индекс самого большого предмета, подходящего по размеру для упаковки в коробку
                                self.id = self.pred.loc[(self.pred['packed']==False)
                                                & (self.pred['prediction']==x)
                                                & (self.pred['volume'] < self.box[1]),'volume'].idxmax()

                
                    # вычитаем объем предмета из объема коробки
                                self.box[1] -= self.pred.loc[self.id, 'volume']
                    
                    # меняем статус предмета на "упакован"
                                self.pred.loc[self.id, 'packed'] = True
                
                    # добавляем sku погруженного в коробку предмета в список sku данной коробки
                                self.list_of_items_in_box.append(self.pred.loc[self.id, 'sku'])

                    # пополняем списки, из которых сформируется таблица на выходе метода
                            self.box_list.append(self.box[0])
                            self.sku_list.append(self.list_of_items_in_box)
                            self.type_list.append(x)
                            
 
        
        self.result = pd.DataFrame(data={'type':self.type_list, 'box':self.box_list, 'goods': self.sku_list}).sort_values(by=['type', 'box']).reset_index(drop=True)
        return self.result
