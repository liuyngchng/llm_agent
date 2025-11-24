--文件信息记录, file_suffix, 0: docx, 1: xlsx
CREATE TABLE "file_info" (
	"id"	INTEGER NOT NULL UNIQUE,
	"fid"	TEXT NOT NULL,
	"uid"	INTEGER,
	"full_path"	TEXT NOT NULL,
	"file_suffix"	INTEGER NOT NULL DEFAULT 0,
	"timestamp"	TEXT NOT NULL,
	PRIMARY KEY("id" AUTOINCREMENT)
);