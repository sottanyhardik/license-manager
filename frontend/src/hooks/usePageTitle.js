import { useEffect } from 'react';
import { useLocation, matchPath } from 'react-router-dom';

const APP_NAME = 'License Manager';

function formatEntityName(entity) {
    if (!entity) return '';
    return entity.split('-').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');
}

const PATH_TITLES = [
    { pattern: '/dashboard',                                    title: 'Dashboard' },
    // Licenses
    { pattern: '/licenses/create',                              title: 'Create License' },
    { pattern: '/licenses/:id/edit',                            title: 'Edit License' },
    { pattern: '/licenses',                                     title: 'Licenses' },
    // Allotments
    { pattern: '/allotments/create',                            title: 'Create Allotment' },
    { pattern: '/allotments/:id/edit',                          title: 'Edit Allotment' },
    { pattern: '/allotments/:id/allocate',                      title: 'Allocate Allotment' },
    { pattern: '/allotments',                                   title: 'Allotments' },
    // Bill of Entries
    { pattern: '/bill-of-entries/:id/generate-transfer-letter', title: 'Transfer Letter' },
    { pattern: '/bill-of-entries/create',                       title: 'Create Bill of Entry' },
    { pattern: '/bill-of-entries/:id/edit',                     title: 'Edit Bill of Entry' },
    { pattern: '/bill-of-entries',                              title: 'Bill of Entry' },
    // Trades
    { pattern: '/trades/create',                                title: 'Create Trade' },
    { pattern: '/trades/:id/edit',                              title: 'Edit Trade' },
    { pattern: '/trades',                                       title: 'Trade In & Out' },
    // Incentive Licenses
    { pattern: '/incentive-licenses/create',                    title: 'Create Incentive License' },
    { pattern: '/incentive-licenses/:id/edit',                  title: 'Edit Incentive License' },
    { pattern: '/incentive-licenses',                           title: 'Incentive Licenses' },
    // License Ledger
    { pattern: '/license-ledger/:id/:companyId',                title: 'Ledger Detail' },
    { pattern: '/license-ledger/:id',                           title: 'Ledger Detail' },
    { pattern: '/license-ledger',                               title: 'License Ledger' },
    // Reports
    { pattern: '/reports/download-license',                     title: 'Download License' },
    { pattern: '/reports/item-pivot',                           title: 'Item Pivot Report' },
    { pattern: '/reports/item-report',                          title: 'Item Report' },
    { pattern: '/reports/parle/sion-e1',                        title: 'SION E1 Report' },
    { pattern: '/reports/parle/sion-e5',                        title: 'SION E5 Report' },
    { pattern: '/reports/parle/sion-e126',                      title: 'SION E126 Report' },
    { pattern: '/reports/parle/sion-e132',                      title: 'SION E132 Report' },
    { pattern: '/reports/expiring-licenses',                    title: 'Expiring Licenses' },
    { pattern: '/reports/active-licenses',                      title: 'Active Licenses' },
    // Uploads
    { pattern: '/ledger-upload',                                title: 'Ledger Upload' },
    // Auth / misc
    { pattern: '/settings',                                     title: 'Settings' },
    { pattern: '/profile',                                      title: 'Profile' },
    { pattern: '/login',                                        title: 'Login' },
    // Masters (dynamic entity)
    {
        pattern: '/masters/:entity/create',
        titleFn: (p) => `Create ${formatEntityName(p.entity)}`,
    },
    {
        pattern: '/masters/:entity/:id/edit',
        titleFn: (p) => `Edit ${formatEntityName(p.entity)}`,
    },
    {
        pattern: '/masters/:entity',
        titleFn: (p) => formatEntityName(p.entity),
    },
];

export function usePageTitle() {
    const location = useLocation();

    useEffect(() => {
        let pageTitle = '';

        for (const route of PATH_TITLES) {
            const match = matchPath({ path: route.pattern, end: true }, location.pathname);
            if (match) {
                pageTitle = route.titleFn ? route.titleFn(match.params) : route.title;
                break;
            }
        }

        document.title = pageTitle ? `${pageTitle} | ${APP_NAME}` : APP_NAME;
    }, [location.pathname]);
}
