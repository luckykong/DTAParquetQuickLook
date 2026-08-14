#import <Foundation/Foundation.h>
#import <Security/Security.h>
#import <bsm/libbsm.h>
#import <signal.h>

@protocol DTAParquetRenderProtocol
- (void)renderFileAtPath:(NSString *)path
               withReply:(void (^)(NSString * _Nullable text,
                                   NSString * _Nullable errorMessage))reply;
@end

static const NSUInteger MaxPreviewOutputBytes = 64 * 1024 * 1024; // 64 MB cap
static NSString * const PreviewExtensionBundleId = @"io.github.dtaparquetquicklook.Preview";
static NSString * const HostAppBundleId = @"io.github.dtaparquetquicklook";

@interface DTAParquetRenderService : NSObject <DTAParquetRenderProtocol>
@end

@implementation DTAParquetRenderService

// Read config.json from the app's Application Support directory. Returns an
// empty dictionary when the file is missing or malformed.
- (NSDictionary *)configDictionary {
    NSString *configPath = [NSHomeDirectory() stringByAppendingPathComponent:
        @"Library/Application Support/DTA Parquet Quick Look/config.json"];
    NSData *data = [NSData dataWithContentsOfFile:configPath];
    if (data == nil) return @{};

    NSError *error = nil;
    id object = [NSJSONSerialization JSONObjectWithData:data options:0 error:&error];
    if (error != nil || ![object isKindOfClass:[NSDictionary class]]) return @{};
    return (NSDictionary *)object;
}

- (NSString * _Nullable)pythonExecutable {
    NSFileManager *fileManager = [NSFileManager defaultManager];
    NSMutableArray<NSString *> *candidates = [NSMutableArray array];

    // 1. Environment variable override (debugging).
    NSString *configured = [[[NSProcessInfo processInfo] environment]
        objectForKey:@"DTA_PARQUET_PYTHON"];
    if (configured.length > 0) [candidates addObject:configured];

    // 2. config.json's "python_path" (set by the settings window).
    NSDictionary *config = [self configDictionary];
    NSString *configPython = config[@"python_path"];
    if ([configPython isKindOfClass:[NSString class]] && configPython.length > 0) {
        [candidates addObject:configPython];
    }

    // 3. Legacy python-path file (kept for backwards compatibility).
    NSString *legacyPath = [NSHomeDirectory() stringByAppendingPathComponent:
        @"Library/Application Support/DTA Parquet Quick Look/python-path"];
    NSString *legacyValue = [NSString stringWithContentsOfFile:legacyPath
                                                       encoding:NSUTF8StringEncoding
                                                          error:nil];
    legacyValue = [legacyValue stringByTrimmingCharactersInSet:
        [NSCharacterSet whitespaceAndNewlineCharacterSet]];
    if (legacyValue.length > 0) [candidates addObject:legacyValue];

    // 4. Common locations (none of which is a personal/developer path).
    NSString *home = NSHomeDirectory();
    [candidates addObjectsFromArray:@[
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

// Whether to show metadata (variable labels, value labels, data label,
// timestamp). Read from config.json; defaults to YES when absent or invalid.
- (BOOL)showMetadata {
    id value = [self configDictionary][@"show_metadata"];
    if (value == nil) return YES;
    if ([value isKindOfClass:[NSNumber class]]) return [(NSNumber *)value boolValue];
    if ([value isKindOfClass:[NSString class]]) {
        NSString *normalized = [[(NSString *)value lowercaseString]
            stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceAndNewlineCharacterSet]];
        return ![@[@"", @"0", @"false", @"no", @"off"] containsObject:normalized];
    }
    return YES;
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
    environment[@"DTA_PARQUET_SHOW_METADATA"] = [self showMetadata] ? @"1" : @"0";
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

    // Read stdout with a hard byte cap so an abnormally wide table (no column
    // limit) cannot balloon memory. Reading in bounded chunks also lets the
    // timeout above interrupt a stuck process.
    NSFileHandle *handle = outputPipe.fileHandleForReading;
    NSMutableData *buffer = [NSMutableData data];
    BOOL truncated = NO;
    while (buffer.length < MaxPreviewOutputBytes) {
        NSData *chunk = [handle readDataOfLength:65536];
        if (chunk.length == 0) break;
        [buffer appendData:chunk];
    }
    if (buffer.length >= MaxPreviewOutputBytes) {
        NSData *probe = [handle readDataOfLength:1];
        if (probe.length > 0) {
            truncated = YES;
            [task terminate]; // enough captured; avoid deadlock on a full pipe
        }
    }

    [task waitUntilExit];
    if (!truncated && task.terminationStatus != 0) {
        reply(nil, [NSString stringWithFormat:@"The preview helper exited with status %d.",
                    task.terminationStatus]);
        return;
    }
    NSString *text = [[NSString alloc] initWithData:buffer encoding:NSUTF8StringEncoding];
    if (text.length == 0) {
        reply(nil, @"The preview helper returned no output.");
        return;
    }
    if (truncated) {
        text = [text stringByAppendingString:@"\n\n(preview output truncated)"];
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

// Accept only connections from our own host app or Quick Look extension.
// This closes the global-name mach lookup to unrelated local processes.
- (BOOL)connectionIsTrusted:(NSXPCConnection *)connection {
    pid_t pid = connection.processIdentifier;

    SecCodeRef code = NULL;
    OSStatus status = SecCodeCopyGuestWithAttributes(
        NULL,
        (__bridge CFDictionaryRef)@{ (__bridge NSString *)kSecGuestAttributePid: @(pid) },
        kSecCSDefaultFlags,
        &code);
    if (status != errSecSuccess || code == NULL) {
        NSLog(@"DTA Parquet Render: could not resolve code for pid %d (%d)", pid, (int)status);
        return NO;
    }

    CFDictionaryRef infoRef = NULL;
    status = SecCodeCopySigningInformation(code, kSecCSSigningInformation, &infoRef);
    CFRelease(code);
    if (status != errSecSuccess || infoRef == NULL) {
        NSLog(@"DTA Parquet Render: could not read signing info (%d)", (int)status);
        return NO;
    }

    NSDictionary *info = (__bridge_transfer NSDictionary *)infoRef;
    NSString *identifier = info[(__bridge NSString *)kSecCodeInfoIdentifier];
    BOOL trusted = [identifier isEqualToString:PreviewExtensionBundleId]
        || [identifier isEqualToString:HostAppBundleId];
    if (!trusted) {
        NSLog(@"DTA Parquet Render: rejected connection from %@", identifier ?: @"<unknown>");
    }
    return trusted;
}

- (BOOL)listener:(NSXPCListener *)listener
 shouldAcceptNewConnection:(NSXPCConnection *)connection {
    if (![self connectionIsTrusted:connection]) {
        return NO;
    }
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
