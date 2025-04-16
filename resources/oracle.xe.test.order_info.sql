--------------------------------------------------------
--  File created - Wednesday-April-16-2025   
--------------------------------------------------------
--------------------------------------------------------
--  DDL for Table ORDER_INFO
--------------------------------------------------------

  CREATE TABLE "TEST"."ORDER_INFO" 
   (	"ID" NUMBER, 
	"订单ID" NUMBER, 
	"省" VARCHAR2(32 BYTE), 
	"公司名称" VARCHAR2(128 BYTE), 
	"商品名称" VARCHAR2(128 BYTE), 
	"年" NUMBER, 
	"创建时间" VARCHAR2(64 BYTE), 
	"支付方式" VARCHAR2(64 BYTE), 
	"支付金额" VARCHAR2(64 BYTE), 
	"月" VARCHAR2(20 BYTE)
   ) SEGMENT CREATION IMMEDIATE 
  PCTFREE 10 PCTUSED 40 INITRANS 1 MAXTRANS 255 NOCOMPRESS LOGGING
  STORAGE(INITIAL 65536 NEXT 1048576 MINEXTENTS 1 MAXEXTENTS 2147483645
  PCTINCREASE 0 FREELISTS 1 FREELIST GROUPS 1 BUFFER_POOL DEFAULT FLASH_CACHE DEFAULT CELL_FLASH_CACHE DEFAULT)
  TABLESPACE "SYSTEM" ;

   COMMENT ON TABLE "TEST"."ORDER_INFO"  IS '燃气销售经营信息表';
REM INSERTING into TEST.ORDER_INFO
SET DEFINE OFF;
Insert into TEST.ORDER_INFO (ID,"订单ID","省","公司名称","商品名称","年","创建时间","支付方式","支付金额","月") values (1,2233445,'广东','广东天然气体有限公司','居民天然气',2025,'2025-04-10','昆仑惠享+','123456','4');
Insert into TEST.ORDER_INFO (ID,"订单ID","省","公司名称","商品名称","年","创建时间","支付方式","支付金额","月") values (2,3342567,'辽宁','辽宁天然气有限公司','工商服务天然气',2024,'2024-05-01','对公转账','6658789','5');
--------------------------------------------------------
--  DDL for Index SYS_C006995
--------------------------------------------------------

  CREATE UNIQUE INDEX "TEST"."SYS_C006995" ON "TEST"."ORDER_INFO" ("ID") 
  PCTFREE 10 INITRANS 2 MAXTRANS 255 
  STORAGE(INITIAL 65536 NEXT 1048576 MINEXTENTS 1 MAXEXTENTS 2147483645
  PCTINCREASE 0 FREELISTS 1 FREELIST GROUPS 1 BUFFER_POOL DEFAULT FLASH_CACHE DEFAULT CELL_FLASH_CACHE DEFAULT)
  TABLESPACE "SYSTEM" ;
--------------------------------------------------------
--  Constraints for Table ORDER_INFO
--------------------------------------------------------

  ALTER TABLE "TEST"."ORDER_INFO" ADD PRIMARY KEY ("ID")
  USING INDEX PCTFREE 10 INITRANS 2 MAXTRANS 255 
  STORAGE(INITIAL 65536 NEXT 1048576 MINEXTENTS 1 MAXEXTENTS 2147483645
  PCTINCREASE 0 FREELISTS 1 FREELIST GROUPS 1 BUFFER_POOL DEFAULT FLASH_CACHE DEFAULT CELL_FLASH_CACHE DEFAULT)
  TABLESPACE "SYSTEM"  ENABLE;
  ALTER TABLE "TEST"."ORDER_INFO" MODIFY ("订单ID" NOT NULL ENABLE);
