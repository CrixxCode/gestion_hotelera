import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ListPayments } from './list-payments';

describe('ListPayments', () => {
  let component: ListPayments;
  let fixture: ComponentFixture<ListPayments>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ListPayments]
    })
    .compileComponents();

    fixture = TestBed.createComponent(ListPayments);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
