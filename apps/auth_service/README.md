# 用户认证服务 (auth_service)

基于 FastAPI 的独立用户认证 HTTP 服务，提供 JSON API 接口。

## 启动

```bash
cd apps/auth_service
python app.py                    # 默认端口 19010
python app.py 19011              # 指定端口
```

生产环境:
```bash
cd apps/auth_service
uvicorn app:app --host 0.0.0.0 --port 19010
```

## API 文档

启动后访问 http://localhost:19010/docs 查看 Swagger 文档。

## API 列表

| 方法 | 路径 | 说明 | 需登录 |
|------|------|------|--------|
| GET | /health | 健康检查 | 否 |
| GET | /api/captcha/generate | 生成验证码 token | 否 |
| GET | /api/captcha/image/{token} | 获取验证码 SVG | 否 |
| POST | /api/auth/login | 用户登录 | 否 |
| POST | /api/auth/register | 用户注册 | 否 |
| POST | /api/auth/verify | 验证 token | 是 |
| GET | /api/auth/me | 获取当前用户信息 | 是 |
| GET | /api/auth/user/{uid} | 查询指定用户 | 是 |
| GET | /api/auth/user/search/{name} | 按用户名搜索 | 是 |

## 调用示例

```bash
# 登录
curl -X POST http://localhost:19010/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"usr":"admin","t":"加密后密码","captcha_code":"1234","captcha_token":"xxx"}'

# 验证 token
curl -X POST http://localhost:19010/api/auth/verify \
  -H "Authorization: Bearer <token>"

# 获取当前用户
curl http://localhost:19010/api/auth/me \
  -H "Authorization: Bearer <token>"
```
