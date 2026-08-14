#import <Cocoa/Cocoa.h>

// Host application: a small settings window for the Quick Look extension.
// It edits config.json (python_path + show_metadata) in the app's
// Application Support directory.

static NSString * const AppSupportName = @"DTA Parquet Quick Look";

@interface AppDelegate : NSObject <NSApplicationDelegate>
@property(nonatomic, strong) NSWindow *window;
@property(nonatomic, strong) NSTextField *pythonPathField;
@property(nonatomic, strong) NSButton *showMetadataCheckbox;
@property(nonatomic, strong) NSTextField *statusLabel;
@end

@implementation AppDelegate

- (NSString *)configDirectory {
    return [NSHomeDirectory() stringByAppendingPathComponent:
        [NSString stringWithFormat:@"Library/Application Support/%@", AppSupportName]];
}

- (NSString *)configPath {
    return [[self configDirectory] stringByAppendingPathComponent:@"config.json"];
}

- (NSMutableDictionary *)loadConfig {
    NSData *data = [NSData dataWithContentsOfFile:[self configPath]];
    if (data == nil) return [NSMutableDictionary dictionary];
    NSError *error = nil;
    id object = [NSJSONSerialization JSONObjectWithData:data
                                                options:NSJSONReadingMutableContainers
                                                  error:&error];
    if (error != nil || ![object isKindOfClass:[NSMutableDictionary class]]) {
        return [NSMutableDictionary dictionary];
    }
    return (NSMutableDictionary *)object;
}

- (void)setStatus:(NSString *)text isError:(BOOL)isError {
    self.statusLabel.stringValue = text;
    self.statusLabel.textColor = isError ? [NSColor systemRedColor]
                                         : [NSColor secondaryLabelColor];
}

- (void)saveConfig:(id)sender {
    NSString *pythonPath = [self.pythonPathField.stringValue
        stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceAndNewlineCharacterSet]];

    NSMutableDictionary *config = [self loadConfig];
    if (pythonPath.length > 0) {
        config[@"python_path"] = pythonPath;
    } else {
        [config removeObjectForKey:@"python_path"];
    }
    config[@"show_metadata"] = @(self.showMetadataCheckbox.state == NSControlStateValueOn);

    NSError *error = nil;
    NSData *data = [NSJSONSerialization dataWithJSONObject:config
                                                   options:NSJSONWritingPrettyPrinted
                                                     error:&error];
    if (data == nil) {
        [self setStatus:[NSString stringWithFormat:@"保存失败: %@", error.localizedDescription]
                isError:YES];
        return;
    }

    NSFileManager *fileManager = [NSFileManager defaultManager];
    [fileManager createDirectoryAtPath:[self configDirectory]
           withIntermediateDirectories:YES
                            attributes:nil
                                 error:nil];
    BOOL ok = [data writeToFile:[self configPath] options:NSDataWritingAtomic error:&error];
    if (ok) {
        [self setStatus:@"已保存。关闭并重新打开预览窗口后生效。" isError:NO];
    } else {
        [self setStatus:[NSString stringWithFormat:@"保存失败: %@", error.localizedDescription]
                isError:YES];
    }
}

- (void)browsePython:(id)sender {
    NSOpenPanel *panel = [NSOpenPanel openPanel];
    panel.canChooseFiles = YES;
    panel.canChooseDirectories = NO;
    panel.allowsMultipleSelection = NO;
    panel.title = @"选择 Python 解释器";
    panel.prompt = @"选择";
    if ([panel runModal] == NSModalResponseOK) {
        self.pythonPathField.stringValue = panel.URL.path;
    }
}

- (void)buildWindow {
    NSRect contentRect = NSMakeRect(0, 0, 560, 210);
    NSWindowStyleMask style = NSWindowStyleMaskTitled
        | NSWindowStyleMaskClosable
        | NSWindowStyleMaskMiniaturizable;
    self.window = [[NSWindow alloc] initWithContentRect:contentRect
                                              styleMask:style
                                                backing:NSBackingStoreBuffered
                                                  defer:NO];
    self.window.title = @"DTA Parquet Quick Look";
    self.window.releasedWhenClosed = NO;

    NSView *content = self.window.contentView;

    NSTextField *pythonLabel = [NSTextField labelWithString:@"Python 解释器路径:"];
    pythonLabel.frame = NSMakeRect(20, 168, 200, 17);
    [content addSubview:pythonLabel];

    self.pythonPathField = [[NSTextField alloc] initWithFrame:NSMakeRect(20, 136, 430, 24)];
    self.pythonPathField.placeholderString = @"/path/to/python";
    [content addSubview:self.pythonPathField];

    NSButton *browseButton = [NSButton buttonWithTitle:@"浏览…"
                                                target:self
                                                action:@selector(browsePython:)];
    browseButton.frame = NSMakeRect(458, 134, 82, 28);
    browseButton.bezelStyle = NSBezelStyleRounded;
    [content addSubview:browseButton];

    self.showMetadataCheckbox = [NSButton buttonWithTitle:@"显示元数据（变量标签、值标签、数据标签）"
                                                   target:nil
                                                   action:nil];
    [self.showMetadataCheckbox setButtonType:NSButtonTypeSwitch];
    self.showMetadataCheckbox.frame = NSMakeRect(20, 96, 520, 20);
    [content addSubview:self.showMetadataCheckbox];

    NSButton *saveButton = [NSButton buttonWithTitle:@"保存"
                                              target:self
                                              action:@selector(saveConfig:)];
    saveButton.frame = NSMakeRect(20, 24, 100, 32);
    saveButton.bezelStyle = NSBezelStyleRounded;
    [content addSubview:saveButton];

    self.statusLabel = [NSTextField labelWithString:@""];
    self.statusLabel.frame = NSMakeRect(130, 24, 410, 32);
    self.statusLabel.lineBreakMode = NSLineBreakByWordWrapping;
    [content addSubview:self.statusLabel];

    // Load current values from config.json.
    NSMutableDictionary *config = [self loadConfig];
    id pythonPath = config[@"python_path"];
    if ([pythonPath isKindOfClass:[NSString class]]) {
        self.pythonPathField.stringValue = pythonPath;
    }
    id showMetadata = config[@"show_metadata"];
    BOOL show = YES;
    if ([showMetadata isKindOfClass:[NSNumber class]]) {
        show = [showMetadata boolValue];
    }
    self.showMetadataCheckbox.state = show ? NSControlStateValueOn : NSControlStateValueOff;

    [self.window center];
}

- (void)applicationDidFinishLaunching:(NSNotification *)notification {
    [self buildWindow];
    [self.window makeKeyAndOrderFront:nil];
    [NSApp activateIgnoringOtherApps:YES];
}

- (BOOL)applicationShouldTerminateAfterLastWindowClosed:(NSApplication *)sender {
    return YES;
}

@end

int main(int argc, const char *argv[]) {
    @autoreleasepool {
        NSApplication *app = [NSApplication sharedApplication];
        [app setActivationPolicy:NSApplicationActivationPolicyRegular];
        AppDelegate *delegate = [[AppDelegate alloc] init];
        app.delegate = delegate;
        [app run];
    }
    return 0;
}
