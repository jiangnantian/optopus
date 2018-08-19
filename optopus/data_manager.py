# -*- coding: utf-8 -*-
from optopus.data_objects import (DataSource, Asset, AssetType, BarDataType, 
                                  IndexDataAsset, OptionChainDataAsset,
                                  PositionData)
from optopus.settings import HISTORICAL_DAYS
from optopus.utils import nan, is_nan, parse_ib_date, format_ib_date
import collections


class DataAdapter():
    pass


class DataManager():
    def __init__(self) -> None:
        self._catalog = {}
        self._data_adapters = {}
        self._data_assets = {}
        self._data_positions = {}

    def add_data_adapter(self,
                         data_adapter: DataAdapter,
                         data_source: DataSource) -> None:
        self._data_adapters[data_source] = data_adapter

    def _change_position(self, p: PositionData) -> None:

        ownership = p.ownership.value if p.ownership else 'NA'
        expiration = format_ib_date(p.expiration) if p.expiration else 'NA'
        strike = str(p.strike) if not is_nan(p.strike) else 'NA'
        right = p.right.value if p.right else 'NA'

        key = p.code + '_' + p.asset_type.value + '_' \
            + expiration + '_' + strike + '_' + right + '_' + ownership

        self._data_positions[key] = p

    def positions(self) -> object:
        position_list = list()
        for k, position in self._data_positions.items():
            d = collections.OrderedDict()
            d['code'] = position.code
            d['asset_type'] = position.asset_type.value
            d['expiration'] = position.expiration
            d['strike'] = position.strike
            d['right'] = position.right.value
            d['ownership'] = position.ownership.value
            d['quantity'] = position.quantity
            d['average_cost'] = position.average_cost
            position_list.append(d)
        return position_list

    def _register_data_asset(self, a: Asset) -> bool:
        
        if a.asset_type == AssetType.Index:
            self._data_adapters[a.data_source].register_index(a)
            self._data_assets[a.asset_id] = IndexDataAsset(a.code, a.data_source)
        elif a.asset_type == AssetType.Option:
            self._data_adapters[a.data_source].register_option(a)
            self._data_assets[a.asset_id] = OptionChainDataAsset(a.underlying,
                                                            a.n_expiration_dates, 
                                                            a.underlying_distance)

    def current(self, assets: list, fields: list) -> object:
        data_assets = list()
        if not isinstance(assets, list):
            #if only receive one asset
            assets = [assets]
        
        # All the assests have the same type
        if not all([t.asset_type == assets[0].asset_type for t in assets]):
            raise ValueError('There are more than one type of asset')

        for asset in assets:
            if asset.asset_id not in self._data_assets:
                self._register_data_asset(asset)

            if asset.asset_type == AssetType.Index:
                self._data_assets[asset.asset_id].current_data = self._data_adapters[asset.data_source].fetch_current_data_index(asset)
            if asset.asset_type == AssetType.Option:
                self._data_assets[asset.asset_id].current_data = self._data_adapters[asset.data_source].fetch_current_data_option(asset)
            
            for e in self._data_assets[asset.asset_id].current_data:
                data_assets.append(e)

        values_list = list()
        for data in data_assets:
            d = collections.OrderedDict()
            d['code'] = getattr(data, 'code')
            # If the asset is a Option, add others default fields
            if data.asset_type == AssetType.Option:
                d['expiration'] = getattr(data, 'expiration')
                d['strike'] = getattr(data, 'strike')
                d['right'] = getattr(data, 'right')
                
            for field in fields:
                if hasattr(data, field):
                  d[field] = getattr(data, field)
            values_list.append(d)
            
        return values_list
    
    def historical(self,
                   assets: list,
                   fields: list,
                   bar_type: BarDataType) -> object:
        
        data_assets = list()
        if not isinstance(assets, list):
            #if only receive one asset
            assets = [assets]
        
        # All the assests have the same type
        if not all([t.asset_type == assets[0].asset_type for t in assets]):
            raise ValueError('There are more than one type of asset')

        for asset in assets:
            if asset.asset_id not in self._data_assets:
                self._register_data_asset(asset)
            if bar_type == BarDataType.Trades:
                self._data_assets[asset.asset_id].historical_data = self._data_adapters[asset.data_source].fetch_historical_data_asset(asset)
                data = self._data_assets[asset.asset_id].historical_data
                #data = self._data_adapters[asset.data_source].historical(asset)
                #self._data_assets[asset.asset_id].historical_data = data
            elif bar_type == BarDataType.IV:
                self._data_assets[asset.asset_id].historical_IV_data = self._data_adapters[asset.data_source].fetch_historical_IV_data_asset(asset)
                data = self._data_assets[asset.asset_id].historical_IV_data
                #data = self._data_adapters[asset.data_source].historical_IV(asset)
                #self._data_assets[asset.asset_id].historial_IV_data = data        
            for e in data:
                data_assets.append(e)

        values_list = list()
        for data in data_assets:
            d = collections.OrderedDict()
            d['code'] = getattr(data, 'code')
            for field in fields:
                if hasattr(data, field):
                    d[field] = getattr(data, field)
            values_list.append(d)

        return values_list

    def IV_rank(self, asset: Asset, IV_value: float) -> float:
            data_asset = self._data_assets[asset.asset_id]    
            min_IV_values = [b.bar_low for b in data_asset.historical_IV_data]
            max_IV_values = [b.bar_high for b in data_asset.historical_IV_data]
            IV_min = min(min_IV_values) 
            IV_max = max(max_IV_values)
            IV_rank = (IV_value -IV_min) / (IV_max - IV_min) * 100
            return IV_rank
            
    def IV_percentile(self, asset: Asset, IV_value: float) -> float:
            data_asset = self._data_assets[asset.asset_id]
            IV_values = [b.bar_low for b in data_asset.historical_IV_data if b.bar_low < IV_value]
            return len(IV_values) / HISTORICAL_DAYS * 100

            