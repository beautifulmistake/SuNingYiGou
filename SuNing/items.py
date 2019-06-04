# -*- coding: utf-8 -*-

# Define here the models for your scraped items
#
# See documentation in:
# https://doc.scrapy.org/en/latest/topics/items.html

import scrapy


class SuningItem(scrapy.Item):
    # define the fields for your item here like:
    # name = scrapy.Field()
    # 搜索关键字
    keyword = scrapy.Field()
    # 店铺 id
    shop_id = scrapy.Field()
    # 商品 id
    product_id = scrapy.Field()
    # 商品价格
    price = scrapy.Field()
    # 搜索标题
    title = scrapy.Field()
    # 评论数
    comment_num = scrapy.Field()
    # 店铺名称
    shop_name = scrapy.Field()
    # 店铺详情页链接
    shop_detail_url = scrapy.Field()
    # 商品详情页
    product_detail_url = scrapy.Field()
    # 商品图片
    product_pic_url = scrapy.Field()

