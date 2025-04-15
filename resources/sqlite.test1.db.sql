CREATE TABLE "order_info" (
	"id"	INTEGER,
	"订单ID"	INTEGER NOT NULL,
	"省"	TEXT,
	"公司名称"	TEXT,
	"商品名称"	TEXT,
	"年"	INTEGER,
	"月"	INTEGER,
	"创建时间"	TEXT,
	"支付方式"	TEXT,
	"支付金额"	TEXT,
	"支付金额单位"	TEXT,
	PRIMARY KEY("id" AUTOINCREMENT)
)