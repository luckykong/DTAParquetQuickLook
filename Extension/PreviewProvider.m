#import <Foundation/Foundation.h>
#import <QuickLookUI/QuickLookUI.h>
#import <UniformTypeIdentifiers/UniformTypeIdentifiers.h>

@protocol DTAParquetRenderProtocol
- (void)renderFileAtPath:(NSString *)path
               withReply:(void (^)(NSString * _Nullable text,
                                   NSString * _Nullable errorMessage))reply;
@end

@interface DTAParquetPreviewProvider : QLPreviewProvider <QLPreviewingController>
@end

@implementation DTAParquetPreviewProvider

- (void)providePreviewForFileRequest:(QLFilePreviewRequest *)request
                    completionHandler:(void (^)(QLPreviewReply * _Nullable, NSError * _Nullable))handler
API_AVAILABLE(macos(12.0)) {
    NSXPCConnection *connection = [[NSXPCConnection alloc]
        initWithServiceName:@"io.github.dtaparquetquicklook.Render"];
    connection.remoteObjectInterface = [NSXPCInterface interfaceWithProtocol:
        @protocol(DTAParquetRenderProtocol)];

    __block BOOL completed = NO;
    void (^finish)(NSString *) = ^(NSString *html) {
        @synchronized (connection) {
            if (completed) return;
            completed = YES;
        }
        NSData *htmlData = [html dataUsingEncoding:NSUTF8StringEncoding];
        QLPreviewReply *reply = [[QLPreviewReply alloc]
            initWithDataOfContentType:UTTypeHTML
            contentSize:CGSizeMake(1200, 760)
            dataCreationBlock:^NSData * _Nullable(QLPreviewReply *reply,
                                                   NSError **blockError) {
                return htmlData;
            }];
        reply.title = request.fileURL.lastPathComponent;
        handler(reply, nil);
        [connection invalidate];
    };

    connection.interruptionHandler = ^{
        finish([self HTMLForTitle:request.fileURL.lastPathComponent
                             text:@"DATA PREVIEW ERROR\n\nThe rendering service was interrupted."]);
    };
    connection.invalidationHandler = ^{};
    [connection resume];

    id<DTAParquetRenderProtocol> service = [connection
        remoteObjectProxyWithErrorHandler:^(NSError *error) {
            finish([self HTMLForTitle:request.fileURL.lastPathComponent
                                 text:[NSString stringWithFormat:@"DATA PREVIEW ERROR\n\n%@",
                                       error.localizedDescription]]);
        }];
    [service renderFileAtPath:request.fileURL.path
                    withReply:^(NSString *text, NSString *errorMessage) {
        if (text != nil) {
            finish(text);
        } else {
            finish([self HTMLForTitle:request.fileURL.lastPathComponent
                                 text:[NSString stringWithFormat:@"DATA PREVIEW ERROR\n\n%@",
                                       errorMessage ?: @"Unknown rendering error."]]);
        }
    }];
}

- (NSString *)HTMLForTitle:(NSString *)title text:(NSString *)text {
    NSString *escapedTitle = [self escapeHTML:title];
    NSString *escapedText = [self escapeHTML:text];
    return [NSString stringWithFormat:
        @"<!doctype html><html><head><meta charset='utf-8'>"
         "<meta name='viewport' content='width=device-width,initial-scale=1'>"
         "<title>%@</title><style>"
         ":root{color-scheme:light dark}*{box-sizing:border-box}"
         "html,body{margin:0;min-height:100%%}body{padding:18px 20px 28px;"
         "background:Canvas;color:CanvasText;font-family:ui-monospace,SFMono-Regular,"
         "Menlo,Monaco,Consolas,monospace}.title{position:sticky;top:0;z-index:1;"
         "margin:-18px -20px 14px;padding:12px 20px;"
         "border-bottom:1px solid rgba(127,127,127,.35);"
         "border-bottom:1px solid color-mix(in srgb,CanvasText 18%%,transparent);"
         "background:Canvas;background:color-mix(in srgb,"
         "Canvas 94%%,transparent);backdrop-filter:blur(12px);font:600 13px "
         "-apple-system,BlinkMacSystemFont,sans-serif}pre{margin:0;width:max-content;"
         "min-width:100%%;font-size:12px;line-height:1.55;tab-size:4;white-space:pre}"
         "</style></head><body><div class='title'>%@ · first 50 rows · all variables"
         "</div><pre>%@</pre></body></html>",
        escapedTitle, escapedTitle, escapedText];
}

- (NSString *)escapeHTML:(NSString *)value {
    NSString *result = [value stringByReplacingOccurrencesOfString:@"&" withString:@"&amp;"];
    result = [result stringByReplacingOccurrencesOfString:@"<" withString:@"&lt;"];
    result = [result stringByReplacingOccurrencesOfString:@">" withString:@"&gt;"];
    result = [result stringByReplacingOccurrencesOfString:@"\"" withString:@"&quot;"];
    result = [result stringByReplacingOccurrencesOfString:@"'" withString:@"&#39;"];
    return result;
}

@end
