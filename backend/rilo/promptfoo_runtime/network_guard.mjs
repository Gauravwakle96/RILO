// Applied before the dependency import. Node permissions separately deny child
// processes, native addons, and filesystem access outside the allowed directories.
import net from 'node:net';
import tls from 'node:tls';
import http from 'node:http';
import https from 'node:https';
import dns from 'node:dns';
import dgram from 'node:dgram';
import { syncBuiltinESMExports } from 'node:module';

const deny = () => { throw new Error('Network access is disabled in Rilo grading'); };
net.Socket.prototype.connect = deny;
net.connect = net.createConnection = deny;
tls.connect = deny;
http.request = http.get = https.request = https.get = deny;
dns.lookup = dns.resolve = deny;
dgram.createSocket = deny;
globalThis.fetch = deny;
syncBuiltinESMExports();
