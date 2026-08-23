package llm_api_adapter;

import io.netty.bootstrap.ServerBootstrap;
import io.netty.channel.*;
import io.netty.channel.nio.NioEventLoopGroup;
import io.netty.channel.socket.SocketChannel;
import io.netty.channel.socket.nio.NioServerSocketChannel;
import io.netty.handler.codec.http.HttpObjectAggregator;
import io.netty.handler.codec.http.HttpServerCodec;
import io.netty.handler.codec.http.cors.CorsConfig;
import io.netty.handler.codec.http.cors.CorsHandler;
import io.netty.handler.logging.LogLevel;
import io.netty.handler.logging.LoggingHandler;
import io.netty.handler.timeout.IdleStateHandler;
import io.netty.util.concurrent.DefaultThreadFactory;
import llm_api_adapter.config.Config;
import llm_api_adapter.config.ConfigLoader;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.File;
import java.io.IOException;
import java.net.*;
import java.util.ArrayList;
import java.util.Enumeration;
import java.util.List;
import java.util.concurrent.TimeUnit;

public class LlmApiAdapterApplication {

    private static final Logger log = LoggerFactory.getLogger(LlmApiAdapterApplication.class);

    public static void main(String[] args) throws Exception {
        // ── load config ──
        String cfgPath = "config.yml";
        if (!new File(cfgPath).exists()) {
            cfgPath = "cfg.yml";
        }
        Config cfg = ConfigLoader.load(cfgPath);

        // Resolve port: CLI arg > environment > config file > default
        int port = cfg.getPort();
        if (args.length > 0) {
            try { port = Integer.parseInt(args[0]); } catch (NumberFormatException ignored) {}
        }

        // Ensure log directory exists (Log4j2 creates the file, but not the dir)
        File logDir = new File(cfg.getLogFile()).getParentFile();
        if (logDir != null && !logDir.exists()) {
            logDir.mkdirs();
        }
        System.setProperty("log.file", cfg.getLogFile());

        log.info("Starting llm_api_adapter (Netty + Log4j2)...");
        log.info("Upstream URI: {}", cfg.getLlmApiUri());
        log.info("Model: {}", cfg.getLlmModelName());

        // ── Netty bootstrap ──
        EventLoopGroup bossGroup = new NioEventLoopGroup(1, new DefaultThreadFactory("netty-boss"));
        EventLoopGroup workerGroup = new NioEventLoopGroup(0, new DefaultThreadFactory("netty-worker"));

        try {
            CorsConfig corsConfig = HttpHandler.corsConfig();

            ServerBootstrap b = new ServerBootstrap();
            b.group(bossGroup, workerGroup)
                    .channel(NioServerSocketChannel.class)
                    .option(ChannelOption.SO_BACKLOG, 128)
                    .childOption(ChannelOption.SO_KEEPALIVE, true)
                    .childHandler(new ChannelInitializer<SocketChannel>() {
                        @Override
                        protected void initChannel(SocketChannel ch) {
                            ChannelPipeline p = ch.pipeline();
                            p.addLast(new IdleStateHandler(600, 0, 0, TimeUnit.SECONDS));
                            p.addLast(new HttpServerCodec());
                            p.addLast(new HttpObjectAggregator(10 * 1024 * 1024)); // 10MB max body
                            p.addLast(new CorsHandler(corsConfig));
                            p.addLast(new HttpHandler(cfg));
                        }
                    });

            Channel ch = b.bind(port).sync().channel();

            // Print startup message
            String msg = "\n──────────────────────────────────────────────────────────────\n"
                    + String.format("  LLM API Adapter started on port %d\n", port)
                    + "  Set your client's ANTHROPIC_BASE_URL to one of:\n";
            log.info("Service started on port {}. your ANTHROPIC_BASE_URL=", port);
            for (String ip : getLocalIPs()) {
                msg += String.format("          http://%s:%d\n", ip, port);
                log.info("          http://{}:{}", ip, port);
            }
            msg += "──────────────────────────────────────────────────────────────";
            System.out.println(msg);

            log.info("Listening on :{}, upstream={}, model={}", port, cfg.getLlmApiUri(), cfg.getLlmModelName());

            ch.closeFuture().sync();
        } finally {
            bossGroup.shutdownGracefully();
            workerGroup.shutdownGracefully();
            log.info("Server stopped");
        }
    }

    private static List<String> getLocalIPs() {
        List<String> ips = new ArrayList<>();
        List<String> loopback = new ArrayList<>();
        try {
            Enumeration<NetworkInterface> ifaces = NetworkInterface.getNetworkInterfaces();
            while (ifaces.hasMoreElements()) {
                NetworkInterface iface = ifaces.nextElement();
                if (!iface.isUp()) continue;
                Enumeration<InetAddress> addrs = iface.getInetAddresses();
                while (addrs.hasMoreElements()) {
                    InetAddress addr = addrs.nextElement();
                    if (addr instanceof Inet4Address) {
                        if (addr.isLoopbackAddress()) {
                            loopback.add(addr.getHostAddress());
                        } else {
                            ips.add(addr.getHostAddress());
                        }
                    }
                }
            }
        } catch (SocketException ignored) {}
        return ips.isEmpty() ? (loopback.isEmpty() ? java.util.Collections.singletonList("127.0.0.1") : loopback) : ips;
    }
}