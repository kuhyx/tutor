// Copyright (c) 2026 Krzysztof Rudnicki. MIT License.

// e2e_h2proxy: an HTTP/2 (TLS) reverse proxy in front of the RTDB emulator,
// for the agent E2E only (scripts/e2e_sandbox.sh starts it).
//
// Why: the emulator speaks HTTP/1.1, and Chrome opens at most 6 connections
// per host over HTTP/1.1. The session screen holds 6 SSE streams (rev,
// presence, live, meta, msgs, progress), so a Send's PUT never gets a socket
// and the app sits on "Sent; waiting for the PC...". The real database is
// served over HTTP/2, where streams share one connection; this proxy gives
// the e2e app the same. The certificate is self-signed, made at start, and
// the e2e Chrome ignores certificate errors.
//
// Usage: go run e2e_h2proxy.go -listen 127.0.0.1:P -target http://127.0.0.1:D
package main

import (
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/tls"
	"crypto/x509"
	"crypto/x509/pkix"
	"flag"
	"log"
	"math/big"
	"net"
	"net/http"
	"net/http/httputil"
	"net/url"
	"time"
)

// selfSigned makes a throwaway certificate for 127.0.0.1 and localhost.
func selfSigned() tls.Certificate {
	key, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		log.Fatalf("key: %v", err)
	}
	tmpl := x509.Certificate{
		SerialNumber: big.NewInt(time.Now().UnixNano()),
		Subject:      pkix.Name{CommonName: "tutor-e2e"},
		NotBefore:    time.Now().Add(-time.Hour),
		NotAfter:     time.Now().Add(24 * time.Hour),
		DNSNames:     []string{"localhost"},
		IPAddresses:  []net.IP{net.ParseIP("127.0.0.1")},
		KeyUsage:     x509.KeyUsageDigitalSignature,
		ExtKeyUsage:  []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth},
	}
	der, err := x509.CreateCertificate(rand.Reader, &tmpl, &tmpl, &key.PublicKey, key)
	if err != nil {
		log.Fatalf("certificate: %v", err)
	}
	return tls.Certificate{Certificate: [][]byte{der}, PrivateKey: key}
}

func main() {
	listen := flag.String("listen", "", "host:port to serve HTTPS (h2) on")
	target := flag.String("target", "", "the emulator, http://127.0.0.1:D")
	flag.Parse()
	upstream, err := url.Parse(*target)
	if err != nil || *listen == "" || upstream.Host == "" {
		log.Fatal("usage: e2e_h2proxy -listen 127.0.0.1:P -target http://127.0.0.1:D")
	}
	proxy := httputil.NewSingleHostReverseProxy(upstream)
	proxy.FlushInterval = -1 // SSE: pass every event on at once
	direct := proxy.Director
	proxy.Director = func(r *http.Request) {
		direct(r)
		r.Host = upstream.Host // the emulator names its namespace by host
	}
	server := &http.Server{
		Addr:    *listen,
		Handler: proxy,
		TLSConfig: &tls.Config{
			Certificates: []tls.Certificate{selfSigned()},
			NextProtos:   []string{"h2", "http/1.1"},
		},
		ReadHeaderTimeout: 10 * time.Second,
	}
	log.Printf("e2e h2 proxy: https://%s -> %s", *listen, upstream)
	log.Fatal(server.ListenAndServeTLS("", ""))
}
