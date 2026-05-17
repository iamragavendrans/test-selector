export const ENV = {
  orangehrmUrl:
    process.env.ORANGEHRM_URL ||
    'https://opensource-demo.orangehrmlive.com/web/index.php/auth/login',
  orangehrmUsername: process.env.ORANGEHRM_USERNAME || 'Admin',
  orangehrmPassword: process.env.ORANGEHRM_PASSWORD || 'admin123',
  reqresBaseUrl: process.env.REQRES_BASE_URL || 'https://reqres.in/api'
};
