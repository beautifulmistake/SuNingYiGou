"""
根据关键字去苏宁易购中进行搜索,然后将搜去的结果存入文件
"""
import json
import os
import scrapy
from scrapy.exceptions import CloseSpider
from scrapy.signals import spider_closed
from scrapy.spidermiddlewares.httperror import HttpError
from scrapy_redis.spiders import RedisSpider
from twisted.internet.error import TCPTimedOutError, DNSLookupError

from SuNing.items import SuningItem


class SuNingSpider(RedisSpider):
    # 爬虫命名
    name = "SuNing"
    # 启动命令
    redis_key = "SuNingSpider:items"

    def __init__(self, settings):
        super().__init__()
        self.keyword_file_list = os.listdir(settings.get("KEYWORD_PATH"))
        # 请求的URL keyword=搜索关键字    cp=页号从0开始      paging=层数从0开始
        self.base_url = "https://search.suning.com/emall/searchV1Product.do?" \
                        "keyword={0}&pg=01&cp={1}&paging={2}"
        # 获取商品价格的URL
        self.price_url = "https://ds.suning.com/ds/generalForTile/0000000{product_id}__2_{shop_id}-010-2-{shop_id}-1--"
        # 请求头
        self.headers = {
            'Accept': 'text/html, */*; q=0.01',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/'
                          '537.36 (KHTML, like Gecko) Chrome/72.0.3626.109 Safari/537.36',
            # 'Referer': '',
            'X-Requested-With': 'XMLHttpRequest'
        }
        # 商品价格的请求头
        self.price_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/'
                          '537.36 (KHTML, like Gecko) Chrome/72.0.3626.109 Safari/537.36',
            'Host': 'ds.suning.com',
            'Upgrade-Insecure-Requests': '1',
            '': '',
        }
        self.default_value = "暂无信息"

    def parse_err(self, failure):
        """
        处理各种异常,将请求失败的 Request 按照自定义方式进行处理,可以定义方法将失败的 Request 写入文件,也可以重新将其加入请求的队列之中
        :param failure:
        :return:
        """
        if failure.check(TimeoutError, TCPTimedOutError, DNSLookupError):
            # 失败的请求
            request = failure.request
            # 将失败的请求重新加入请求队列
            self.server.rpush(self.redis_key, request)
        if failure.check(HttpError):
            # 获取响应
            response = failure.value.response
            # 重新加入请求队列
            self.server.rpush(self.redis_key, response.url)
        return

    def start_requests(self):
        """
        循环读取文件列表,生成出书请求
        :return:
        """
        # 判断关键字文件存在否
        if not self.keyword_file_list:
            # 抛出异常并关闭爬虫
            raise CloseSpider("需要关键字文件")
        for keyword_file in self.keyword_file_list:
            # 循环获取关键字文件路径
            file_path = os.path.join(self.settings.get("KEYWORD_PATH"), keyword_file)
            # 读取文件
            with open(file_path, 'r', encoding='utf-8') as f:
                for keyword in f.readlines():
                    # 消除关键字末尾的空白字符
                    keyword = keyword.strip()
                    print("查看关键字:", keyword)
                    # 发起请求,cp 为页号 从0开始, paging 为 层数,从0开始
                    yield scrapy.Request(url=self.base_url.format(keyword, str(0), str(0)), headers=self.headers,
                                         callback=self.parse, errback=self.parse_err,
                                         meta={'keyword': keyword, 'cp': 0, 'paging': 0})

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        # 获取配置信息
        settings = crawler.settings
        # 爬虫信息
        spider = super(SuNingSpider, cls).from_crawler(crawler, settings, *args, **kwargs)
        # 获取信号,终止爬虫
        crawler.signals.connect(spider.spider_closed, signal=spider_closed)
        # 返回spider,不然无法 运行 start_requests 方法
        return spider

    def spider_closed(self, spider):
        """
        爬虫关闭时执行的操作
        :param spider:
        :return:
        """
        # 输出日志关闭爬虫
        self.logger.info('Spider closed : %s', spider.name)
        # 根据具体情况添加这两个方法
        # spider.record_file.write("]")
        # spider.record_file.close()

    def parse(self, response):
        """
        解析响应,获取目标字段数据
        :param response:
        :return:
        """
        if response.status == 200:
            print("查看响应:", response.text)
            # 获取当前搜索关键字
            keyword = response.meta['keyword']
            # 获取当前搜索的层数
            paging = response.meta['paging']
            print("查看当前的层数:", paging)
            # 获取当前的页号
            cp = response.meta['cp']
            print("查看当前的页号:", cp)
            # 获取信息列表 //div[@id="product-wrap"]//ul/li  2019/5/21改变如下获取方式
            info_list = response.xpath('//li|//div[@id="product-wrap"]//ul/li')
            for info in info_list:
                # 店铺/商品 id  获取 li标签的 id 属性值  格式如下: shop_id - product_id
                shop_id, product_id = info.xpath('./@id').extract_first().split('-')
                print(shop_id, product_id)
                # 标题
                title = info.xpath('.//div[@class="product-box"]/div[@class="res-info"]/'
                                   'div[@class="title-selling-point"]/a/descendant-or-self::text()').extract()
                # print(title)
                # 评论数
                comment_num = info.xpath('.//div[@class="product-box"]/div[@class="res-info"]/'
                                         'div[@class="evaluate-old clearfix"]/div/a/i/text()').extract_first()
                # 店铺名称
                shop_name = info.xpath('.//div[@class="product-box"]/div[@class="res-info"]/'
                                       'div[@class="store-stock"]/a/text()').extract_first()
                # 店铺详情页链接,需要进行拼接 https:
                shop_detail_url = info.xpath('.//div[@class="product-box"]/div[@class="res-info"]/'
                                             'div[@class="store-stock"]/a/@href').extract_first()
                # 商品详情页
                product_detail_url = info.xpath('.//div[@class="product-box"]/div[@class="res-info"]/'
                                                'div[@class="title-selling-point"]/a/@href').extract_first()
                # 商品图片
                product_pic_url = info.xpath('.//div[@class="product-box"]/'
                                             'div[@class="res-img"]//img/@src').extract_first()
                # 如果需要采集详情页的数据在此增加详情页的解析函数
                # 操作item
                # item['keyword'] = keyword
                # # 店铺 id
                # item['shop_id'] = shop_id if shop_id else self.default_value
                # # 商品 id
                # item['product_id'] = product_id if product_id else self.default_value
                # # 搜索标题
                # item['title'] = " ".join(title).strip() if title else self.default_value
                # # 评论数
                # item['comment_num'] = comment_num if comment_num else self.default_value
                # # 店铺名称
                # item['shop_name'] = shop_name if shop_name else self.default_value
                # # 店铺详情页链接
                # item['shop_detail_url'] = "https:" + shop_detail_url if shop_detail_url else self.default_value
                # # 商品详情页
                # item['product_detail_url'] = "https:" + product_detail_url if\
                #     product_detail_url else self.default_value
                # # 商品图片
                # item['product_pic_url'] = "https:" + product_pic_url if product_pic_url else self.default_value
                # yield item
                if shop_id and product_id:
                    yield scrapy.Request(url=self.price_url.format(product_id=product_id, shop_id=shop_id),
                                         headers=self.price_headers,
                                         meta={'keyword': keyword, 'shop_id': shop_id, 'product_id': product_id,
                                               'comment_num': comment_num, 'shop_name': shop_name, 'shop_detail_url':
                                                   shop_detail_url, 'product_detail_url': product_detail_url,
                                               'product_pic_url': product_pic_url, 'title': title},
                                         callback=self.parse_price, errback=self.parse_err)
            # 判断当前的层数 和 页号
            if cp < 50 and paging < 3:
                # 层数加一
                paging += 1
                # 每一页需要请求四层,每满足四层时,增加一页,同时层数归零
                yield scrapy.Request(url=self.base_url.format(keyword, str(cp), str(paging)), headers=self.headers,
                                     callback=self.parse, errback=self.parse_err,
                                     meta={'keyword': keyword, 'cp': cp, 'paging': paging})
            # 判断是否该增加页号, paging 代表层数  cp 代表页号
            if paging == 3 and cp < 49:
                # 层数归零,页号增加一
                cp += 1
                print("准备采集第%s页" % cp)
                yield scrapy.Request(url=self.base_url.format(keyword, str(cp), str(0)), headers=self.headers,
                                     callback=self.parse, errback=self.parse_err,
                                     meta={'keyword': keyword, 'cp': cp, 'paging': 0})

    def parse_price(self, response):
        """
        解析价格信息
        :param response:
        :return:
        """
        if response.status == 200:
            print(response.text)
            # 创建 item
            item = SuningItem()
            # 获取结果
            res = json.loads(response.text, encoding='utf-8')
            # 获取价格
            price = res.get("rs")[0].get("price")
            # 获取 response meta 信息
            keyword = response.meta['keyword']
            shop_id = response.meta['shop_id']
            product_id = response.meta['product_id']
            title = response.meta['title']
            comment_num = response.meta['comment_num']
            shop_name = response.meta['shop_name']
            shop_detail_url = response.meta['shop_detail_url']
            product_detail_url = response.meta['product_detail_url']
            product_pic_url = response.meta['product_pic_url']
            # 给 item 赋值
            item['keyword'] = keyword if keyword else self.default_value
            item['shop_id'] = shop_id if shop_id else self.default_value
            item['product_id'] = product_id if product_id else self.default_value
            item['title'] = " ".join([i.strip() for i in title if i]).strip() if title else self.default_value
            item['price'] = price if price else self.default_value
            item['comment_num'] = comment_num if comment_num else self.default_value
            item['shop_name'] = shop_name if shop_name else self.default_value
            item['shop_detail_url'] = "https:" + shop_detail_url if shop_detail_url else self.default_value
            item['product_detail_url'] = "https:" + product_detail_url if product_detail_url else self.default_value
            item['product_pic_url'] = "https:" + product_pic_url if product_pic_url else self.default_value
            yield item
