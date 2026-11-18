/// Desktop sign-in from the PC server's seeded session (the shared
/// `rtdb_relay` package).
library;

export 'package:rtdb_relay/rtdb_relay.dart'
    show
        adoptWrapperCredentials,
        fetchWrapperPassphrase,
        kSyncCredentialsRoute,
        kSyncPassphraseRoute,
        uidOfIdToken;
