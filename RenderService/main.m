#import <Foundation/Foundation.h>
#import <signal.h>

@protocol DTAParquetRenderProtocol
- (void)renderFileAtPath:(NSString *)path
               withReply:(void (^)(NSString * _Nullable text,
                                   NSString * _Nullable errorMessage))reply;
@end

@interface DTAParquetRenderService : NSObject <DTAParquetRenderProtocol>
@end

@implementation DTAParquetRenderService

- (NSString * _Nullable)pythonExecutable {
    NSFileManager *fileManager = [NSFileManager defaultManager];
    NSMutableArray<NSString *> *candidates = [NSMutableArray array];

    NSString *configured = [[[NSProcessInfo processInfo] environment]
        objectForKey:@"DTA_PARQUET_PYTHON"];
    if (configured.length > 0) [candidates addObject:configured];

    NSString *configPath = [NSHomeDirectory() stringByAppendingPathComponent:
        @"Library/Application Support/DTA Parquet Quick Look/python-path"];
    NSString *configValue = [NSString stringWithContentsOfFile:configPath
                                                       encoding:NSUTF8StringEncoding
                                                          error:nil];
    configValue = [configValue stringByTrimmingCharactersInSet:
        [NSCharacterSet whitespaceAndNewlineCharacterSet]];
    if (configValue.length > 0) [candidates addObject:configValue];

    NSString *home = NSHomeDirectory();
    [candidates addObjectsFromArray:@[
        [home stringByAppendingPathComponent:
            @"Softwares/miniconda3/envs/smallProjects/bin/python"],
        [home stringByAppendingPathComponent:
            @".conda/envs/dta-parquet-quicklook/bin/python"],
        [home stringByAppendingPathComponent:
            @"miniconda3/envs/dta-parquet-quicklook/bin/python"],
        [home stringByAppendingPathComponent:
            @"anaconda3/envs/dta-parquet-quicklook/bin/python"],
        @"/opt/homebrew/bin/python3",
        @"/usr/local/bin/python3",
        @"/usr/bin/python3"
    ]];

    for (NSString *candidate in candidates) {
        NSString *expanded = [candidate stringByExpandingTildeInPath];
        if ([fileManager isExecutableFileAtPath:expanded]) return expanded;
    }
    return nil;
}

- (void)renderFileAtPath:(NSString *)path
               withReply:(void (^)(NSString *, NSString *))reply {
    NSURL *scriptURL = [[NSBundle mainBundle] URLForResource:@"data_preview"
                                               withExtension:@"py"];
    if (scriptURL == nil) {
        reply(nil, @"The bundled data preview helper is missing.");
        return;
    }

    NSString *pythonPath = [self pythonExecutable];
    if (pythonPath == nil) {
        reply(nil, @"No usable Python interpreter was found. See README.md for setup instructions.");
        return;
    }

    NSTask *task = [[NSTask alloc] init];
    NSPipe *outputPipe = [NSPipe pipe];
    task.executableURL = [NSURL fileURLWithPath:pythonPath];
    task.arguments = @[scriptURL.path, @"--html", path];
    task.standardOutput = outputPipe;
    task.standardError = [NSFileHandle fileHandleWithNullDevice];
    NSMutableDictionary<NSString *, NSString *> *environment =
        [[[NSProcessInfo processInfo] environment] mutableCopy];
    environment[@"HOME"] = NSHomeDirectory();
    environment[@"LANG"] = @"en_US.UTF-8";
    environment[@"LC_ALL"] = @"en_US.UTF-8";
    task.environment = environment;

    NSError *launchError = nil;
    if (![task launchAndReturnError:&launchError]) {
        reply(nil, launchError.localizedDescription);
        return;
    }

    __weak NSTask *weakTask = task;
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(15 * NSEC_PER_SEC)),
                   dispatch_get_global_queue(QOS_CLASS_UTILITY, 0), ^{
        NSTask *runningTask = weakTask;
        if (runningTask != nil && runningTask.running) {
            pid_t pid = runningTask.processIdentifier;
            [runningTask terminate];
            dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)NSEC_PER_SEC),
                           dispatch_get_global_queue(QOS_CLASS_UTILITY, 0), ^{
                if (runningTask.running) kill(pid, SIGKILL);
            });
        }
    });

    NSData *data = [outputPipe.fileHandleForReading readDataToEndOfFile];
    [task waitUntilExit];
    if (task.terminationStatus != 0) {
        reply(nil, [NSString stringWithFormat:@"The preview helper exited with status %d.",
                    task.terminationStatus]);
        return;
    }
    NSString *text = [[NSString alloc] initWithData:data encoding:NSUTF8StringEncoding];
    if (text.length == 0) {
        reply(nil, @"The preview helper returned no output.");
        return;
    }
    reply(text, nil);
}

@end

@interface ServiceDelegate : NSObject <NSXPCListenerDelegate>
@property(nonatomic, strong) DTAParquetRenderService *service;
@end

@implementation ServiceDelegate

- (instancetype)init {
    self = [super init];
    if (self) self.service = [[DTAParquetRenderService alloc] init];
    return self;
}

- (BOOL)listener:(NSXPCListener *)listener
 shouldAcceptNewConnection:(NSXPCConnection *)connection {
    connection.exportedInterface = [NSXPCInterface interfaceWithProtocol:
        @protocol(DTAParquetRenderProtocol)];
    connection.exportedObject = self.service;
    [connection resume];
    return YES;
}

@end

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        ServiceDelegate *delegate = [[ServiceDelegate alloc] init];
        NSXPCListener *listener = [NSXPCListener serviceListener];
        listener.delegate = delegate;
        [listener resume];
        [[NSRunLoop currentRunLoop] run];
    }
    return 0;
}
