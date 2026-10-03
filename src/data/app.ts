export const app = {
  name: 'NextGen mParivahan',
  developer: 'National Informatics Centre.',
  tagline: 'Complete Transport Solution for Citizen',
  icon: 'https://play-lh.googleusercontent.com/UPyefodA-z6CpCFyQ6f2Gf4v2_qOdP-VroqRh-S4xKL6uKD7stMPKq4goEESGZe3mlsAS-oD9RljiDv7mJDUXrk=s256-rw',
  rating: '3.7',
  reviews: '7L',
  // Supply an authorized, signed APK here. No real APK has been provided yet.
  apkUrl: '/app.apk',
  apkFileName: 'NextGenmParivahan.apk',
  website: 'https://parivahan.gov.in/',
  supportEmail: 'helpdesk-mparivahan@gov.in',
  playStoreUrl: 'https://play.google.com/store/apps/details?id=com.nic.mparivahan',
};

// These are the original screenshot assets published with the app listing.
const screenshotIds = [
  'JtFWJ080xwdOrL_T17155pmDmCQ9CFYb2T4mQfoOMdBp7v7q-RNNj34iykGZH1O0WBePwC2MmOzaJ9Dsl-F6DQ',
  'MZCJQNj6VvZdqTKXNWy0JjGbmPgB7K8rqg-pHj8i7JN3HQ9Mh_S-_x7-xam8SlAk2tC9EwQUxPZPvsJ4LeQbHVA',
  'J2GFMSotwFS0RcKdSWgSQnEKkOlV_YgmolO2HQ7PFyPLp9vbUoYPq0SFcqGiu6i8hB1DobCvFdHOEt6tJAePuA',
  'iSww52ZWwO92FQjJXzx4tw9YcQwGb7AqwKhpZ_Xyw2RR-tOuVvxfA6frdUxhztlxlWnI4EGmbqVGean4RJLe9i4',
  'Vo73Gic-eCRlXt7hvkoHEPmsAvSI08wDigxnWcuTl_hC_MtP3pr_NoXT9KlhZn_irmEr-etEgWiuuEP48ksVIg',
  'wCdzrA0i_z1pP_2HjXy6u1HdupMSznTwvVlpo7nnWX2kOiYefmImKjuPjHzmRlH344wL5IM9YVQL5VcmksUcgw',
  '3DBV5T4UxbjTvPkEofUWwOBWZ7NVyd-yHfYweSsnPhbpMrewulejeUT-cHVv478NHx8Pnb99uy3sycNAEL0U',
];

const screenshotNames = [
  'Welcome to NextGen mParivahan',
  'Sign in to your account',
  'Vehicle and transport services',
  'Citizen Sentinel',
  'Your transport transactions',
  'Your digital vehicle documents',
  'More mParivahan services',
];

export const screenshots = screenshotIds.map((id, index) => ({
  src: `https://play-lh.googleusercontent.com/${id}=w400-h800-rw`,
  fullSrc: `https://play-lh.googleusercontent.com/${id}=w1000-h1800-rw`,
  alt: screenshotNames[index],
  fallback: index < 4
    ? `https://cdn.soft112.com/mparivahan/00/00/0H/FB/00000HFBGP/pad_screenshot_${index}.webp`
    : '',
}));

export const vehicleDetails = [
  'Owner name and registration date',
  'Registering authority and vehicle class',
  'Make, model, fuel type and vehicle age',
  'Insurance and fitness validity',
];

export const stats = {
  rating: app.rating,
  reviews: app.reviews,
  ratingCount: app.reviews,
  // Requested reference figures, not a live count of this website's downloads.
  downloads: '50M+',
  ratingBars: [
    { stars: 5, pct: 62 },
    { stars: 4, pct: 14 },
    { stars: 3, pct: 8 },
    { stars: 2, pct: 5 },
    { stars: 1, pct: 11 },
  ],
};

export type Review = {
  id: string;
  name: string;
  initial: string;
  color: string;
  date: string;
  rating?: number;
  text: string;
  helpful?: number;
  reply?: string;
  replyDate?: string;
};

// Published excerpts from the official listing. Individual stars were not available.
export const reviews: Review[] = [
  {
    id: 'harshil-karani-2026-09-16',
    name: 'Harshil Karani',
    initial: 'H',
    color: '#8e24aa',
    date: '16 September 2026',
    text: 'Not working, every time I login it says unexpected error or says you are logging in from different device. Doesn\'t work when you need it the most. tried reinstalling too still doesn\'t work. cleared cache too. It worked well in the past but now it just doesn\'t.',
    helpful: 3,
    reply: 'Hi, Sorry about the inconvenience. Try clearing the cache or reinstalling the app. In case the issue still persists, kindly send the error screenshot to helpdesk-mparivahan@gov.in along with the contact details so that we check this.',
    replyDate: '15 September 2026',
  },
  {
    id: 'adit-newah-2026-07-20',
    name: 'Adit Newah',
    initial: 'A',
    color: '#1e88e5',
    date: '20 July 2026',
    text: 'Was better, got worse. I had my vehicle details stored in the app for quite some time now. However when i wanted to check something about my vehicle now i can\'t find the info anymore. So, i tried adding my vehicle again just to get prompted to enter OTP which just has a validity of 30secs.',
  },
  {
    id: 'uday-kiran-2026-07-25',
    name: 'uday kiran reddy Anumula',
    initial: 'U',
    color: '#00897b',
    date: '25 July 2026',
    text: 'This app doesn\'t even allow me to sign up. What\'s the purpose if it doesn\'t have bare minimum maintainance? It\'s been three days and it still shows same error all the times. Tried clearing cache, reinstalled app several times, tried signing up at midnight when the app traffic is low. None of it works.',
  },
];

