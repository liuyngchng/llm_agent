create database if not exists test;

CREATE TABLE `test`.`order_info` (
	'id'	    INTEGER,
	'订单ID'	    INTEGER NOT NULL,
	'省'	    VARCHAR(32),
	'公司名称'	VARCHAR(128),
	'商品名称'	VARCHAR(128),
	'年'	    INTEGER,
	'创建时间'	VARCHAR(64),
	'支付方式'	VARCHAR(64),
	'支付金额'	DOUBLE,
	PRIMARY KEY('id' AUTOINCREMENT)
)