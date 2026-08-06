describe('home page', () => {
  it('has a heading', () => {
    cy.visit('/');
    cy.contains('h1', 'Home');
  });
});
